import difflib
import random
import os

import discord
from discord import Embed, Color, ButtonStyle, Option, OptionChoice, AutocompleteContext, ApplicationContext
from discord.ui import Button, View
from discord.ext import commands
from discord.ext.commands import slash_command
from typing import List, Union, Tuple
from urllib.parse import quote

from models.card_models import Card, Path, all_paths

PATHS = all_paths()


def find_card(card_name: str) -> Union[Tuple[Card, Path], Tuple[None, None]]:
    for path in PATHS:
        card = path.card_by_name(card_name)
        if card:
            return card, path
    return None, None


def path_by_name(valid_paths: List[Path], path_name: str) -> Path:
    return next((p for p in valid_paths if p.name == path_name), None)


def card_url(card_name: str, path_name: str) -> str:
    base_url = "https://raw.githubusercontent.com/ShardlessBun/glorybound_cards/"
    version_string = os.environ["CARD_VERSION"]
    url = f"{base_url}{quote(version_string)}/{quote(path_name)}/{quote(card_name)}.png"
    return url


def path_options() -> List[OptionChoice]:
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


class CardButton(Button):
    card: Card

    def __init__(self, card: Card, *args, **kwargs):
        kwargs["label"] = card.name
        kwargs["custom_id"] = card.name
        kwargs["style"] = ButtonStyle.secondary if card.linked else ButtonStyle.primary
        super(CardButton, self).__init__(*args, **kwargs)
        self.card = card

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: GloryBaseView = self.view

        view.enable_all_items()
        self.disabled = True
        embed = embed_from_card(self.card, view.path)

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
        assert self.view is not None
        view: GloryBaseView = self.view
        h_path = next(p for p in PATHS if p.name == "Heirloom")

        view.enable_all_items()
        self.disabled = True
        embed = embed_from_card(self.card, h_path)

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
        assert self.view is not None
        view: GloryBaseView = self.view

        view.enable_all_items()
        if isinstance(view, TournamentPackView):
            view.path = self.path
            view.children_from_path(self.path)
        self.disabled = True
        embed = embed_from_path(self.path)

        await interaction.response.edit_message(embed=embed, view=view)


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


class CardsCog(commands.Cog, name="CardsCog"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        packview = TournamentPackView(heirlooms=heirlooms, paths=randpaths)
        embed = embed_from_path(randpaths[0])

        packview.message = await ctx.respond(embed=embed, view=packview, ephemeral=hidden)


def setup(bot: commands.Bot):
    bot.add_cog(CardsCog(bot))
