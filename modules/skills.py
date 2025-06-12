# skills.py
import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SkillEffect:
    type: str
    value: int
    duration: Optional[int] = None
    stat: Optional[str] = None

@dataclass
class Skill:
    name: str
    description: str
    level_required: int
    cooldown: int
    sp_cost: int
    effects: list[SkillEffect]
    target_type: str  # 'self', 'single', 'area'

class SkillManager:
    def __init__(self, skills_file='game_data/skills.json'):
        self.skills_file = skills_file
        self.skills = self.load_skills()

    def load_skills(self):
        try:
            with open(self.skills_file, 'r') as f:
                data = json.load(f)
                return self._process_skills_data(data)
        except FileNotFoundError:
            logging.error(f"Skills file not found: {self.skills_file}")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Error parsing skills file: {self.skills_file}")
            return {}

    def _process_skills_data(self, data: Dict) -> Dict:
        processed_skills = {}
        for class_name, class_data in data.items():
            processed_skills[class_name] = {}
            for skill_data in class_data.get('skills', []):
                effects = [SkillEffect(**effect) for effect in skill_data.get('effects', [])]
                skill = Skill(
                    name=skill_data['name'],
                    description=skill_data['description'],
                    level_required=skill_data['level_required'],
                    cooldown=skill_data['cooldown'],
                    sp_cost=skill_data['sp_cost'],
                    effects=effects,
                    target_type=skill_data.get('target_type', 'single')
                )
                processed_skills[class_name][skill.name.lower()] = skill
        return processed_skills

    def get_skill(self, class_name: str, skill_name: str) -> Optional[Skill]:
        class_skills = self.skills.get(class_name.lower(), {})
        return class_skills.get(skill_name.lower())

    def get_available_skills(self, class_name: str, level: int) -> list[Skill]:
        class_skills = self.skills.get(class_name.lower(), {})
        return [skill for skill in class_skills.values() if skill.level_required <= level]

    def can_use_skill(self, character: Dict, skill: Skill) -> tuple[bool, str]:
        if character.get('level', 1) < skill.level_required:
            return False, f"You need to be level {skill.level_required} to use this skill."
            
        if character['stats'].get('SP', 0) < skill.sp_cost:
            return False, f"You need {skill.sp_cost} SP to use this skill."
            
        cooldowns = character.get('cooldowns', {})
        if skill.name in cooldowns:
            remaining = cooldowns[skill.name] - time.time()
            if remaining > 0:
                return False, f"This skill is still on cooldown for {int(remaining)} seconds."
                
        return True, ""

    def use_skill(self, skill: Skill, character: Dict, target: Optional[Dict], 
                 room_manager: Any, client_socket: Any, combat_manager: Any) -> bool:
        can_use, message = self.can_use_skill(character, skill)
        if not can_use:
            client_socket.sendall(message.encode())
            return False

        # Apply skill cost and cooldown
        character['stats']['SP'] -= skill.sp_cost
        character.setdefault('cooldowns', {})[skill.name] = time.time() + skill.cooldown

        success = False
        for effect in skill.effects:
            if effect.type == "damage":
                success = combat_manager.apply_skill_damage(character, target, effect.value, client_socket)
            elif effect.type == "buff":
                success = combat_manager.apply_buff(character, effect.stat, effect.value, effect.duration, client_socket)
            elif effect.type == "area_damage":
                success = combat_manager.apply_area_damage(character, effect.value, room_manager, client_socket)

        return success

    def apply_passive_skills(self, character: Dict):
        """Apply passive skill effects to character stats."""
        class_name = character.get('class', '').lower()
        level = character.get('level', 1)
        available_skills = self.get_available_skills(class_name, level)
        
        for skill in available_skills:
            for effect in skill.effects:
                if effect.type == "passive":
                    stat = effect.stat
                    if stat in character['stats']:
                        character['stats'][stat] += effect.value

# Update skills.json structure with the new format:
EXAMPLE_SKILLS_JSON = {
    "wanderer": {
        "skills": [
            {
                "name": "Quick Slash",
                "description": "A swift attack dealing additional damage.",
                "level_required": 2,
                "cooldown": 5,
                "sp_cost": 10,
                "target_type": "single",
                "effects": [
                    {
                        "type": "damage",
                        "value": 10
                    }
                ]
            },
            {
                "name": "Blade Flurry",
                "description": "A flurry of blades that hits all enemies.",
                "level_required": 4,
                "cooldown": 8,
                "sp_cost": 15,
                "target_type": "area",
                "effects": [
                    {
                        "type": "area_damage",
                        "value": 8
                    }
                ]
            },
            {
                "name": "Battle Stance",
                "description": "Increase your strength temporarily.",
                "level_required": 6,
                "cooldown": 20,
                "sp_cost": 25,
                "target_type": "self",
                "effects": [
                    {
                        "type": "buff",
                        "stat": "Strength",
                        "value": 5,
                        "duration": 30
                    }
                ]
            }
        ]
    }
}
