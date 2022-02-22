import glob
import re
import sys
import typing

import strictyaml as yaml
from strictyaml import Map, MapPattern, Str, Seq, Int, Bool, Optional, CommaSeparated, Regex


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


schema = Map({
    'path': Str(),
    'colors': Regex(r'[0-9a-fA-F]{6}\s*-\s*[0-9a-fA-F]{6}'),
    'resources': Regex(r'[WSFX]{3}'),
    Optional('extras'): Str(),
    'cards': Seq(
        MapPattern(
            Str(), Map({
                'cost': Regex(r'[SWFAX]*'),
                Optional('types'): CommaSeparated(Regex(r'oneshot|permanent|innate|heirloom|support')),
                Optional('linked'): Str(),
                Optional('linked type'): Str(),
                Optional('linked short'): Bool(),
                Optional('path card name'): Str(),
                'text': Str(),
                Optional('purchase'): Int(),
                Optional('upgrade cost'): Int(),
                Optional('upgrade'): Str(),
                Optional('big art'): Bool(),
                Optional('designer'): Str(),
            })
        )
    ),
    # "c": EmptyDict() | Seq(MapPattern(Str(), Str())),
})


class Card(object):
    def __init__(self, d):
        name, d = d.popitem()

        class MyDict(dict):
            def __missing__(self, key):
                return None

            def __getitem__(self, key):
                val = dict.__getitem__(self, key)
                if isinstance(val, str):
                    return val.strip().replace('\n', '\n\n')
                return val

        d = MyDict(d)
        self.name = name
        self.cost = d['cost']
        self.text = d['text']
        self.types = [t.strip() for t in (d['types'] or [])]
        if '\\sequence' in self.text:
            self.types.append('sequence')
        self.linked = d['linked']
        self.linked_type = d['linked type']
        self.linked_short = d['linked short']
        self.path_card_name = d['path card name'] or self.name
        self.linked_to = []
        self.purchase = d['purchase']
        self.upgrade_cost = d['upgrade cost']
        self.upgrade = d['upgrade']
        self.big_art = d['big art']
        self.designer = d['designer']

    def __str__(self):
        return f'<{self.name} {{{self.cost}}} [{self.purchase}]:\n  - ({", ".join(self.types)}) \n  - {repr(self.text)} \n  - [{self.upgrade_cost}: {repr(self.upgrade)}]>'


class Path(object):
    def __init__(self, name, colors, resources, cards, extras=None):
        self.name = name
        self.colors = colors
        self.resources = resources
        self.cards = cards
        self.extras = extras

    @classmethod
    def from_file(cls, filename):
        with open(filename, 'r') as file:
            text = file.read()

        def fix_string_stuff(text):
            text = text.split('\n')
            return '\n'.join(
                [re.sub("^(\s+)([a-zA-Z ]+:)\s*$", lambda m: m.group(1) + m.group(2) + " >\n" + m.group(1) + "  ", line)
                 for line in text])

        # print(text)
        # text = fix_string_stuff(text)
        # print(text)

        config = yaml.load(text, schema)
        data = config.data
        # data = yaml.load(text)
        # print(repr(data))

        name = data['path']
        colors = tuple([c.strip() for c in data['colors'].split('-')])
        resources = data['resources']
        cards = [Card(card) for card in data['cards']]
        extras = data.get('extras', None)
        # print(*cards, sep='\n')
        path = Path(name, colors, resources, cards, extras)
        path.build_links()
        return path

    def card_by_name(self, name):
        matches = [c for c in self.cards if c.name == name]
        if len(matches) > 0:
            return matches[0]
        else:
            return None

    def build_links(self):
        for c in self.cards:
            if c.linked:
                if '{' in c.linked:
                    linked_cards = re.findall(r"\{(.*?)\}", c.linked)
                else:
                    linked_cards = [c.linked]
                for l in linked_cards:
                    self.card_by_name(l).linked_to.append(c)


def all_paths() -> typing.List[Path]:
    paths = [Path.from_file(f) for f in glob.glob('paths/*.yaml')]

    for path in paths:
        for card in path.cards:
            if card.linked:
                linked_to = [c for c in path.cards if card.linked.find(c.name) > -1]
            else:
                linked_to = [c for c in path.cards if (c.linked and c.linked.find(card.name) > -1)]
            card.linked_to = linked_to if len(linked_to) > 0 else None

    return paths
