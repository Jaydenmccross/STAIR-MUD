# modules/spells.py

import logging
import json

class SpellManager:
    def __init__(self, spells_file='game_data/spells.json'):
        self.spells_file = spells_file
        self.spells = self.load_spells()

    def load_spells(self):
        """
        Load spells from the spells.json file.
        """
        try:
            with open(self.spells_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Spells file not found: {self.spells_file}")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Failed to parse spells file: {self.spells_file}")
            return {}

    def get_spell(self, spell_name):
        """
        Retrieve spell data by name.
        """
        spell_name = spell_name.lower()
        return self.spells.get(spell_name)

    def cast_spell(self, spell_name, caster, target):
        """
        Execute the casting logic of a spell, consuming AP and applying effects.
        """
        spell = self.get_spell(spell_name)
        if not spell:
            return f"Spell '{spell_name}' does not exist."

        if caster['stats']['AP'] < spell['ap_cost']:
            return "Not enough AP to cast the spell."

        # Deduct AP cost from caster
        caster['stats']['AP'] -= spell['ap_cost']

        # Apply spell effects to the target
        effects = spell.get('effects', {})
        for stat, value in effects.items():
            target['stats'][stat] = min(target['stats'][stat] + value, target['stats'][f"Max_{stat}"])

        return f"Successfully cast {spell_name} on {target['name']}!"

