import asyncio
import datetime
import difflib
import os
import random
from timeit import default_timer as timer
from typing import List, Union, Tuple, Dict, Optional
from urllib.parse import quote

import aiopg.sa
import discord
import sqlalchemy.engine.row
from discord import Embed, Color, ButtonStyle, InputTextStyle, Option, OptionChoice, AutocompleteContext, \
    ApplicationContext, Interaction
from discord.commands import SlashCommandGroup, permissions
from discord.ext import commands
from discord.ext.commands import slash_command
from discord.ui import Button, View, Modal, InputText, Select
from sqlalchemy import null, and_

from init import GloryBot
from models.card_models import Card, Path, all_paths
from models.db import card_ruling, pick_table, pick_submission_table

PATHS = all_paths()
GAME_DEV_ROLE = 792601590208659456
BOT_COMMANDER_ROLE = 939316017165897828
DEV_ROLE = 946492656706531328


def find_card(card_name: str) -> Union[Tuple[Card, Path], Tuple[None, None]]:
    for path in PATHS:
        card = path.card_by_name(card_name)
        if card:
            return card, path
    return None, None


def is_designer(member: discord.Member) -> bool:
    if member.get_role(GAME_DEV_ROLE) or member.id == 208388527401074688:
        return True
    return False


def path_by_name(valid_paths: List[Path], path_name: str) -> Path:
    return next((p for p in valid_paths if p.name == path_name), None)


def card_url(card_name: str, path_name: str) -> str:
    base_url = "https://raw.githubusercontent.com/ShardlessBun/glorybound_cards/"
    version_string = os.environ["CARD_VERSION"]
    url = f"{base_url}{quote(version_string)}/{quote(path_name)}/{quote(card_name)}.png"
    return url


def path_options() -> List[OptionChoice]:
    """Filters out the Heirloom path and formats the options for slash_commands"""
    return [OptionChoice(p.name, p.name) for p in PATHS if p.name != "Heirloom"]


async def autocomplete_cardname(ctx: AutocompleteContext) -> List[str]:
    """
    Sends a list of autocomplete options back to Discord based on the partial card name provided

    :param ctx: The AutocompleteContext of the interaction
    :returns List[str]: A list of the closest matches to the provided value
    """

    cards = {card.name.lower(): card.name for path in PATHS for card in path.cards}
    card_name = ctx.value.lower()

    if len(card_name) <= 3:
        cutoff = 0
    elif 3 < len(card_name) <= 6:
        cutoff = 0.3
    else:
        cutoff = 0.5
    closest = difflib.get_close_matches(card_name, list(cards.keys()), n=10, cutoff=cutoff)

    filtered = list(filter(lambda c: card_name in c, closest))
    no_matches = list(filter(lambda c: card_name not in c, closest))
    filtered.extend(no_matches)

    closest = [cards[c] for c in filtered]
    return closest


def embed_from_path(path: Path) -> Embed:
    color = Color(int(path.colors[0], 16))
    embed = Embed(title=f"Path of the {path.name}", color=color)
    embed.set_image(url=card_url(path.name, path.name))

    return embed


def embed_from_card(card: Card, path: Path) -> Embed:
    if card.linked:
        color = Color(int(path.colors[1], 16))
    else:
        color = Color(int(path.colors[0], 16))
    embed = Embed(title=card.name, color=color)
    embed.set_image(url=card_url(card.name, path.name))

    return embed


def ruling_embed_from_card(card: Card, path: Path) -> Embed:
    if card.linked:
        color = Color(int(path.colors[1], 16))
    else:
        color = Color(int(path.colors[0], 16))
    embed = Embed(title=f"Card Rulings - *{card.name}*", color=color, description="--------------------")
    embed.set_thumbnail(url=card_url(card.name, path.name))

    return embed


class CardButton(Button):
    card: Card

    def __init__(self, card: Card, *args, **kwargs):
        kwargs["label"] = card.name
        kwargs["custom_id"] = card.name
        kwargs["style"] = ButtonStyle.secondary if card.linked else ButtonStyle.primary
        super(CardButton, self).__init__(*args, **kwargs)
        self.card = card

    async def callback(self, interaction: discord.Interaction):
        start = timer()
        assert self.view is not None
        view: GloryBaseView = self.view

        view.enable_all_items()
        self.disabled = True
        embed = embed_from_card(self.card, view.path)

        end = timer()
        print(f"{interaction.user.name}#{interaction.user.discriminator} clicked on card [ {self.custom_id} ] "
              f"in view [ {type(view)} ]. Response time: [ {end - start}s ]")
        await interaction.response.edit_message(embed=embed, view=view)


class HeirloomButton(Button):
    heirloom: Card

    def __init__(self, card: Card, *args, **kwargs):
        kwargs["label"] = card.name
        kwargs["custom_id"] = card.name
        kwargs["style"] = ButtonStyle.secondary
        super(HeirloomButton, self).__init__(*args, **kwargs)
        self.card = card

    async def callback(self, interaction: discord.Interaction):
        start = timer()
        assert self.view is not None
        view: GloryBaseView = self.view
        h_path = next(p for p in PATHS if p.name == "Heirloom")

        view.enable_all_items()
        self.disabled = True
        embed = embed_from_card(self.card, h_path)

        end = timer()
        print(f"{interaction.user.name}#{interaction.user.discriminator} clicked on heirloom [ {self.custom_id} ] "
              f"in view [ {type(view)} ]. Response time: [ {end - start}s ]")
        await interaction.response.edit_message(embed=embed, view=view)


class PathButton(Button):
    path: Path

    def __init__(self, path: Path, *args, **kwargs):
        kwargs["label"] = path.name
        kwargs["custom_id"] = path.name
        kwargs["style"] = ButtonStyle.success
        super(PathButton, self).__init__(*args, **kwargs)
        self.path = path

    async def callback(self, interaction: discord.Interaction):
        start = timer()
        assert self.view is not None
        view: GloryBaseView = self.view

        view.enable_all_items()
        if isinstance(view, TournamentPackView):
            view.path = self.path
            view.children_from_path(self.path)
        self.disabled = True
        embed = embed_from_path(self.path)

        end = timer()
        print(f"{interaction.user.name}#{interaction.user.discriminator} clicked on path [ {self.custom_id} ] "
              f"in view [ {type(self.view)} ]. Response time: [ {end - start}s ]")
        await interaction.response.edit_message(embed=embed, view=view)


class ErrorEmbed(Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Error:"
        self.color = Color.brand_red()


class SubmissionEmbed(Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Response Submitted:"
        self.color = Color.blurple()


class GloryBaseView(View):
    message: discord.Interaction
    path: Path

    def __init__(self, *args, **kwargs):
        super(GloryBaseView, self).__init__(*args, **kwargs)

    def enable_all_items(self):
        for item in self.children:
            item.disabled = False

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True

    async def on_timeout(self) -> None:
        print("Interaction timed out")
        if self.message and len(self.children) > 1:
            self.disable_all_items()
            await self.message.edit_original_message(content="Timed out", view=self)


class CardView(GloryBaseView):
    children: List[CardButton]

    def __init__(self, card: Card, path: Path, timeout=300.0):
        super().__init__(timeout=timeout)
        self.path = path
        self.add_item(CardButton(card=card, custom_id=card.name, disabled=True))
        for c in (card.linked_to or []):
            self.add_item(CardButton(card=c, custom_id=c.name))


class PathView(GloryBaseView):
    children: List[Union[CardButton, PathButton]]

    def __init__(self, path: Path, timeout=300.0):
        super().__init__(timeout=timeout)
        self.path = path
        self.add_item(PathButton(path=path, custom_id=path.name, disabled=True, row=0))
        for c in (path.cards or []):
            self.add_item(CardButton(card=c, custom_id=c.name, row=2 if c.linked else 1))


class TournamentPackView(GloryBaseView):
    children: List[Union[CardButton, PathButton, HeirloomButton]]
    paths: List[Path]

    def __init__(self, heirlooms: List[Card], paths: List[Path], timeout=300.0):
        super().__init__(timeout=timeout)
        self.paths = paths
        self.path = paths[0]

        # First add the heirlooms
        for heirloom in heirlooms:
            self.add_item(HeirloomButton(card=heirloom, custom_id=heirloom.name, disabled=False, row=0))
        # Then the paths
        for p in paths:
            self.add_item(PathButton(path=p, custom_id=p.name, disabled=True if p == self.path else False, row=1))
        # And finally the path cards
        self.children_from_path(self.path)

    def children_from_path(self, path: Path):
        items_to_remove = []
        for child in self.children:
            if child.row > 1:
                items_to_remove.append(child)
        for item in items_to_remove:
            self.remove_item(item)

        for c in (path.cards or []):
            self.add_item(CardButton(card=c, custom_id=c.name, row=3 if c.linked else 2))


class WeeklyPickView(View):
    # View can get everything it needs from the component interaction & database queries
    db: aiopg.sa.Engine
    last_clicked: Dict[discord.Member, datetime.datetime]

    def __init__(self, db: aiopg.sa.Engine):
        super().__init__(timeout=None)
        self.db = db
        self.last_clicked = {}

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True

    async def get_active_pick(self, guild_id: int) -> sqlalchemy.engine.Row:
        async with self.db.acquire() as conn:
            results = await conn.execute(
                pick_table.select()
                    .where((pick_table.c.guild_id == guild_id) and (
                        pick_table.c.end_ts is None or pick_table.c.end_ts > datetime.datetime.utcnow()))
                    .order_by(pick_table.c.id.desc()))
            row = await results.first()  # Just in case multiple rows are somehow returned
        return row

    @discord.ui.button(label="View Pack", custom_id=f"view_weekly_pick", style=ButtonStyle.primary)
    async def view_callback(self, button: Button, interaction: discord.Interaction):
        # Bit of a cooldown to prevent this from getting spammed
        if interaction.user in self.last_clicked:
            if datetime.datetime.utcnow() - self.last_clicked[interaction.user] < datetime.timedelta(minutes=2):
                await interaction.response.send_message(
                    "Error: Please wait a couple minutes before clicking this button again", ephemeral=True)
                return
            else:
                self.last_clicked[interaction.user] = datetime.datetime.utcnow()
        else:
            self.last_clicked[interaction.user] = datetime.datetime.utcnow()

        row = await self.get_active_pick(interaction.guild_id)

        # Translate db row to cards and paths
        heirlooms = [find_card(h)[0] for h in [row["heirloom0"], row["heirloom1"], row["heirloom2"]]]
        paths = [path_by_name(PATHS, p) for p in [row["path0"], row["path1"], row["path2"]]]

        # Set up the embed and view
        pack_view = TournamentPackView(heirlooms=heirlooms, paths=paths)
        embed = embed_from_path(paths[0])

        pack_view.message = await interaction.response.send_message(embed=embed, view=pack_view, ephemeral=True)

    @discord.ui.button(label="Submit your pick!", custom_id=f"submit_weekly_pick", style=ButtonStyle.primary)
    async def submit_callback(self, button: Button, interaction: discord.Interaction):

        pick_row = await self.get_active_pick(interaction.guild_id)
        submit_view = SubmitPickView(
            db=self.db,
            pick_id=pick_row.id,
            heirlooms=[pick_row["heirloom0"], pick_row["heirloom1"], pick_row["heirloom2"]],
            paths=[pick_row["path0"], pick_row["path1"], pick_row["path2"]])

        await interaction.response.send_message(content="Make your picks below", view=submit_view, ephemeral=True)


class SubmitPickView(GloryBaseView):
    selected_heirloom = str
    selected_paths = List[str]
    pick_id: int
    db: aiopg.sa.Engine

    class HeirloomSelect(Select):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        async def callback(self, interaction: Interaction):
            self.view.selected_heirloom = self.values[0]
            print(f"Values selected: {self.values}")
            await interaction.response.defer()

    class PathsSelect(Select):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        async def callback(self, interaction: Interaction):
            self.view.selected_paths = self.values
            print(f"Values selected: {self.values}")
            await interaction.response.defer()

    class SubmitPickButton(Button):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def verify_selections(self) -> Tuple[bool, str]:
            if self.view.selected_heirloom == "Circlet of Obsession":
                result = len(self.view.selected_paths) == 1
                reason = f"Only 1 path can be selected with {self.view.selected_heirloom}"
            elif self.view.selected_heirloom == "Explorer's Pack":
                result = len(self.view.selected_paths) == 3
                reason = f"All three paths must be selected with {self.view.selected_heirloom}"
            else:
                result = len(self.view.selected_paths) == 2
                reason = f"You must select exactly two paths with {self.view.selected_heirloom}"

            return result, reason

        async def callback(self, interaction: Interaction):
            print(f"Submitting values:\n"
                  f"    Heirloom: {self.view.selected_heirloom}\n"
                  f"    Paths: {self.view.selected_paths}")

            validated, reason = self.verify_selections()

            # Also check whether the user has submitted a response for this pick already
            async with self.view.db.acquire() as conn:
                results = await conn.execute(pick_submission_table.select()
                                             .where(and_(pick_submission_table.c.pick_id == self.view.pick_id,
                                                         pick_submission_table.c.user_id == interaction.user.id)))
                if await results.first():
                    validated = False
                    reason = f"Only one submission allowed per weekly pick per person"
                    self.view.disable_all_items()

            if not validated:
                # Validation has failed, so throw an error
                embed = ErrorEmbed(description=reason)
            else:
                embed = SubmissionEmbed(description=f"Heirloom: {self.view.selected_heirloom}\n"
                                                    f"Paths: {', '.join(self.view.selected_paths)}")
                # Sorting the paths before submitting keeps the data nice and tidy in the database later
                selected_paths = sorted(self.view.selected_paths)
                path_dict = dict(enumerate(selected_paths))
                async with self.view.db.acquire() as conn:
                    await conn.execute(pick_submission_table.insert().values(
                        pick_id=self.view.pick_id,
                        user_id=interaction.user.id,
                        heirloom=self.view.selected_heirloom,
                        path1=path_dict[0],
                        path2=path_dict.get(1),
                        path3=path_dict.get(2),
                    ))
                self.view.disable_all_items()

            await interaction.response.edit_message(embed=embed, view=self.view)

    def __init__(self, db: aiopg.sa.Engine, pick_id: int, heirlooms: List[str], paths: List[str]):
        super().__init__()
        self.db = db
        self.pick_id = pick_id
        self.selected_heirloom = None
        self.selected_paths = []
        self.add_item(self.HeirloomSelect(
            custom_id="heirloom",
            placeholder="Pick an heirloom",
            options=[discord.SelectOption(label=h, value=h) for h in heirlooms],
            row=0
        ))

        min_selected = 1 if "Circlet of Obsession" in heirlooms else 2
        max_selected = 3 if "Explorer's Pack" in heirlooms else 2
        self.add_item(self.PathsSelect(
            custom_id="paths",
            placeholder="Select your paths",
            options=[discord.SelectOption(label=p, value=p) for p in paths],
            min_values=min_selected,
            max_values=max_selected,
            row=1
        ))

        self.add_item(self.SubmitPickButton(
            style=ButtonStyle.primary,
            label="Submit",
            custom_id="Submit",
            row=2
        ))

    async def on_timeout(self) -> None:
        self.disable_all_items()


class AddRulingModal(Modal):
    _author: str
    _engine: aiopg.sa.Engine
    _card_name: str

    def __init__(self, author: str, db: aiopg.sa.Engine, card_name: str, *args, **kwargs):
        super().__init__(title=f"Add ruling: {card_name}", *args, **kwargs)
        self._author = author
        self._engine = db
        self._card_name = card_name

        self.add_item(
            InputText(label="Ruling Text", placeholder="Text goes here",
                      style=InputTextStyle.paragraph, max_length=400))

    async def callback(self, interaction: discord.Interaction):
        async with self._engine.acquire() as conn:
            await conn.execute(card_ruling.insert().values(
                card_name=self._card_name,
                ruling_text=self.children[0].value,
                author=self._author)
            )
        await interaction.response.send_message(f"Ruling added for card **{self._card_name}**")


class CardsCog(commands.Cog, name="CardsCog"):
    bot: GloryBot

    def __init__(self, bot: GloryBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(0.5)
        self.bot.add_view(WeeklyPickView(self.bot.db))

    @slash_command(name="card",
                   description="Displays a card and all cards linked to it")
    async def card_image(self, ctx: ApplicationContext, card_name: Option(str, "Card to be displayed", required=True,
                                                                          autocomplete=autocomplete_cardname)):
        card, path = find_card(card_name)
        if not card:
            await ctx.respond(f"Error: card \'{card_name}\' not found", ephemeral=True)
            return

        cardview = CardView(card, path)
        embed = embed_from_card(card, path)

        cardview.message = await ctx.respond(embed=embed, view=cardview)

    @slash_command(name="path",
                   description="Display an entire path")
    async def path_image(self, ctx: ApplicationContext, path_name: Option(str, "Path to be displayed", required=True,
                                                                          choices=path_options())):
        path = next((p for p in PATHS if p.name == path_name), None)

        pathview = PathView(path)
        embed = embed_from_path(path)

        pathview.message = await ctx.respond(embed=embed, view=pathview)

    @slash_command(name="random",
                   description="Get a random card, heirloom, or path")
    async def rand_card(self, ctx: ApplicationContext, card_type: Option(str, "Type of card to choose from",
                                                                         required=True,
                                                                         choices=["card", "heirloom", "path"])):
        if card_type == "card":
            r_cardname = random.choice([card.name for path in PATHS if path.name != "Heirloom" for card in path.cards])
            card, path = find_card(r_cardname)
            view = CardView(card=card, path=path)
            embed = embed_from_card(card, path)
        elif card_type == "heirloom":
            heirlooms = next(p for p in PATHS if p.name == "Heirloom")
            r_heirloom = random.choice(heirlooms.cards)
            view = CardView(card=r_heirloom, path=heirlooms)
            embed = embed_from_card(r_heirloom, heirlooms)
        else:
            r_path = random.choice([path for path in PATHS])
            view = PathView(path=r_path)
            embed = embed_from_path(r_path)

        view.message = await ctx.respond(embed=embed, view=view)

    @slash_command(name="tournamentpack",
                   description="Generates a combination of three heirlooms and three paths to simulate a tournament")
    async def tournament_pack(self, ctx: ApplicationContext,
                              hidden: Option(bool, "Whether this should be hidden from other users. True by default.",
                                             required=False, default=True)):
        heirlooms = random.sample(path_by_name(PATHS, 'Heirloom').cards, 3)
        randpaths = random.sample([p for p in PATHS if p.name != 'Heirloom'], 3)

        pack_view = TournamentPackView(heirlooms=heirlooms, paths=randpaths)
        embed = embed_from_path(randpaths[0])

        pack_view.message = await ctx.respond(embed=embed, view=pack_view, ephemeral=hidden)

    @slash_command(name="rulings",
                   description="Look up rulings for the specified card")
    async def card_ruling(self,
                          ctx: ApplicationContext,
                          card_name: Option(str, "Card to be displayed", required=True,
                                            autocomplete=autocomplete_cardname),
                          add_remove: Option(str, "DEVELOPERS ONLY: add or remove a card ruling", required=False,
                                             choices=["add", "remove"])):
        # Make sure the card actually exists
        card, path = find_card(card_name)
        if not card:
            await ctx.respond(f"Error: card \'{card_name}\' not found", ephemeral=True)
            return

        # Start with the admin options
        if add_remove == "add":
            if ctx.author.get_role(GAME_DEV_ROLE) is None and ctx.author.id != 208388527401074688:
                await ctx.respond(f"Error: you are not authorized to add card rulings")

            ruling_modal = AddRulingModal(author=ctx.author.name, db=self.bot.db, card_name=card_name)
            await ctx.response.send_modal(ruling_modal)
        elif add_remove == "remove":
            if ctx.author.get_role(GAME_DEV_ROLE) is None and ctx.author.id != 208388527401074688:
                await ctx.respond(f"Error: you are not authorized to remove card rulings")

            await ctx.respond(f"This is where Alesha should implement removing rulings")

        # And now for the "real" functionality
        async with self.bot.db.acquire() as conn:
            query = (
                card_ruling.select()
                           .where(card_ruling.c.card_name == card_name)
                           .order_by(card_ruling.c.created_ts.desc())
            )
            embed = ruling_embed_from_card(card, path)
            row_count = 0
            async for row in conn.execute(query):
                row_count += 1
                embed.add_field(name=f"{row.author} - {row.created_ts.strftime('%m/%d/%Y')}:",
                                value=row.ruling_text, inline=False)
            if row_count > 0:
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"No card rulings found for **{card_name}**")

    # Weekly pick stuff
    weekly_pick = SlashCommandGroup("weekly_pick", "Commands related to weekly picks")

    async def get_active_pick(self, guild_id: int) -> sqlalchemy.engine.Row:
        async with self.bot.db.acquire() as conn:
            results = await conn.execute(
                pick_table.select()
                          .where(pick_table.c.guild_id == guild_id)
                          .where(pick_table.c.end_ts == null())
                          .order_by(pick_table.c.id.desc()))
            row = await results.first()  # Just in case multiple rows are somehow returned
            print(row)
        return row

    @weekly_pick.command(name="create",
                         description="Creates a new weekly pick in the current channel")
    @permissions.has_any_role(GAME_DEV_ROLE, BOT_COMMANDER_ROLE, DEV_ROLE)
    async def create_picks(self, ctx: ApplicationContext):
        if row := await self.get_active_pick(ctx.guild_id):
            await ctx.respond(f"Error, only one weekly pick can be active in a server at a time. "
                              f"Use `/{ctx.command.full_parent_name} end` to end the current weekly pick.")
            return

        # Determine the pack
        heirloom_path = path_by_name(PATHS, 'Heirloom')
        heirlooms = random.sample(heirloom_path.cards, 3)
        randpaths = random.sample([p for p in PATHS if p.name != 'Heirloom'], 3)

        # Build the embed
        embed = Embed(title=f"Weekly Pick for {datetime.datetime.utcnow().strftime('%m/%d/%Y')}",
                      description=f"Click the \"View Pack\" button below to view the heirlooms and paths in more detail"
                                  f", or \"Submit Pick\" to submit your pick "
                                  f"and don't forget to discuss your choices below!")
        embed.add_field(name="Heirlooms:", inline=False, value='\n'.join(
            [f"- {card.name}" for card in heirlooms]
        ))
        embed.add_field(name="Paths:", inline=False, value='\n'.join(
            [f"- Path of the **{path.name}**" for path in randpaths]
        ))
        embed.set_thumbnail(
            url="https://raw.githubusercontent.com/ShardlessBun/glorybound_cards/main/cardback-rainbow.png")

        # Display the embed & buttons
        msg: discord.Interaction = await ctx.respond(embed=embed, view=WeeklyPickView(db=self.bot.db))

        original = await msg.original_message()
        try:
            await original.pin(reason="Pinning weekly pick")
        except discord.Forbidden as E:
            await ctx.send(embed=ErrorEmbed(description="Unable to pin message. Likely because I'm missing the "
                                                        "\"Manage Messages\" permission."))

        # Finally, write everything to the database
        try:
            async with self.bot.db.acquire() as conn:
                result = await conn.execute(pick_table.insert().values(
                    heirloom0=heirlooms[0].name,
                    heirloom1=heirlooms[1].name,
                    heirloom2=heirlooms[2].name,
                    path0=randpaths[0].name,
                    path1=randpaths[1].name,
                    path2=randpaths[2].name,
                    creator_id=ctx.author.id,
                    guild_id=ctx.guild_id,
                    channel_id=msg.channel.id,
                    message_id=original.id,
                    created_ts=datetime.datetime.utcnow()
                ))
        except aiopg.sa.Error as E:
            print(E)
            await msg.delete_original_message()
            await ctx.send(content=f"Error in creating weekly pick")

    @weekly_pick.command(name="submit",
                         description="Prompts you to submit your picks for the week")
    async def submit_picks(self, ctx: ApplicationContext):
        if (row := await self.get_active_pick(ctx.guild_id)) is None:
            await ctx.respond(f"Error: there is no weekly pick active in this server"
                              f"Use `/{ctx.command.full_parent_name} create` to start a new weekly pick.")
            return

        submit_view = SubmitPickView(
            db=self.bot.db,
            pick_id=row.id,
            heirlooms=[row["heirloom0"], row["heirloom1"], row["heirloom2"]],
            paths=[row["path0"], row["path1"], row["path2"]])

        await ctx.respond(content="Make your picks below", view=submit_view, ephemeral=True)

    @weekly_pick.command(name="view",
                         description="View a tournament pack of this week's picks")
    async def view_picks(self, ctx: ApplicationContext):
        if (row := await self.get_active_pick(ctx.guild_id)) is None:
            await ctx.respond(f"Error: there is no weekly pick active in this server"
                              f"Use `/{ctx.command.full_parent_name} create` to start a new weekly pick.")
            return

        # Translate db row to cards and paths
        heirlooms = [find_card(h)[0] for h in [row["heirloom0"], row["heirloom1"], row["heirloom2"]]]
        paths = [path_by_name(PATHS, p) for p in [row["path0"], row["path1"], row["path2"]]]

        # Set up the embed and view
        pack_view = TournamentPackView(heirlooms=heirlooms, paths=paths)
        embed = embed_from_path(paths[0])

        pack_view.message = await ctx.respond(embed=embed, view=pack_view, ephemeral=True)

    @weekly_pick.command(name="end",
                         description="Closes out the open weekly pick")
    @permissions.has_any_role(GAME_DEV_ROLE, BOT_COMMANDER_ROLE, DEV_ROLE)
    async def end_pick(self, ctx: ApplicationContext):
        if (row := await self.get_active_pick(ctx.guild_id)) is None:
            await ctx.respond(f"Error: there is no weekly pick active in this server"
                              f"Use `/{ctx.command.full_parent_name} create` to start a new weekly pick.")
            return

        async with self.bot.db.acquire() as conn:
            await conn.execute(pick_table.update().values({"end_ts": datetime.datetime.utcnow()})
                               .where(pick_table.c.guild_id == ctx.guild_id))

        channel: discord.TextChannel = discord.utils.get(ctx.guild.channels, id=row["channel_id"])
        if channel:
            try:
                msg: discord.Message = await channel.fetch_message(row["message_id"])
            except discord.NotFound:
                print(f"Couldn't find weekly pick with message_id [ {row['message_id']} ] to unpin/disable, skipping")
            else:
                pick_view = WeeklyPickView.from_message(msg)
                for child in pick_view.children:
                    child.disabled = True
                if msg.pinned:
                    await msg.unpin()
                await msg.edit(view=pick_view)
        else:
            print(f"Couldn't find channel_id [ {row['channel_id']} ] containing weekly pick to unpin/disable, skipping")

        await ctx.respond(content=f"Weekly pick started on {row.created_ts.strftime('%m/%d/%Y')} closed")


def setup(bot: GloryBot):
    bot.add_cog(CardsCog(bot))
