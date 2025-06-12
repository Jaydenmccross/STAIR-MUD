# effects.py

import random
import time
from enum import Enum
from typing import Dict, List, Any, Optional
import threading
import logging

class EffectType(Enum):
    """Defines the different types of effects available in the game."""
    DAMAGE = "damage"
    HEALING = "healing"
    BUFF = "buff"
    DEBUFF = "debuff"
    DOT = "dot"  # Damage over time
    HOT = "hot"  # Healing over time
    STUN = "stun"
    SILENCE = "silence"

class TargetType(Enum):
    """Defines the different types of targeting available for effects."""
    SELF = "self"
    SINGLE_MOB = "single_mob"
    ALL_MOBS = "all_mobs"
    SINGLE_CHARACTER = "single_character"
    ALL_CHARACTERS = "all_characters"

class EffectHandler:
    def __init__(self):
        self.active_effects = {}
        self._lock = threading.RLock()

    def apply_effect(self, effect_name, targets, value, duration=0, **kwargs):
        """Wrapper for the global apply_effect function."""
        apply_effect(effect_name, targets, value, duration, **kwargs)

def apply_damage(target, value, combat_manager=None, client_socket=None, is_mob=False):
    """Deals damage to the target and handles death."""
    old_hp = target['stats']['HP']
    target['stats']['HP'] = max(0, old_hp - value)
    
    if is_mob:
        client_socket.sendall(f"{target['name']} hits you for {value} damage!\n".encode())
    else:
        client_socket.sendall(f"You hit {target['name']} for {value} damage!\n".encode())

    if target['stats']['HP'] <= 0:
        if is_mob:
            combat_manager.handle_player_death(target, client_socket, combat_manager.account_manager)
        else:
            combat_manager.handle_combat_victory(target, client_socket, combat_manager.room_manager, 
                                               combat_manager.mob_manager, combat_manager.account_manager, 
                                               combat_manager.item_manager)

def apply_heal(target, value, client_socket=None):
    """Heals the target."""
    old_hp = target['stats']['HP']
    max_hp = target['stats']['Max_HP']
    
    target['stats']['HP'] = min(max_hp, old_hp + value)
    healing_done = target['stats']['HP'] - old_hp
    
    if healing_done > 0 and client_socket:
        client_socket.sendall(f"{target['name']} is healed for {healing_done} HP.\n".encode())

def apply_buff(target, stat, value, duration, combat_session=None):
    """Applies a temporary buff to a stat with duration handling."""
    if 'buffs' not in target:
        target['buffs'] = []
        
    target['buffs'].append((stat, value, duration))
    
    if combat_session:
        combat_session['status_effects'].append({
            "type": "buff",
            "target": target,
            "stat": stat,
            "value": value,
            "end_time": time.time() + duration
        })
        client_socket = combat_session.get('client_socket')
        if client_socket:
            client_socket.sendall(
                f"{target['name']}'s {stat} is increased by {value} for {duration} seconds.\n".encode()
            )

def apply_debuff(target, stat, value, duration, combat_session=None):
    """Applies a temporary debuff to a stat with duration handling."""
    if 'debuffs' not in target:
        target['debuffs'] = []
        
    target['debuffs'].append((stat, value, duration))
    
    if combat_session:
        combat_session['status_effects'].append({
            "type": "debuff",
            "target": target,
            "stat": stat,
            "value": value,
            "end_time": time.time() + duration
        })
        client_socket = combat_session.get('client_socket')
        if client_socket:
            client_socket.sendall(
                f"{target['name']}'s {stat} is decreased by {value} for {duration} seconds.\n".encode()
            )

def apply_dot(target, value, duration, combat_session=None, client_socket=None):
    """Applies damage over time effect."""
    if combat_session:
        combat_session['status_effects'].append({
            "type": "dot",
            "target": target,
            "value": value,
            "end_time": time.time() + duration
        })
        if client_socket:
            client_socket.sendall(
                f"{target['name']} is afflicted with a damage over time effect!\n".encode()
            )

def apply_hot(target, value, duration, combat_session=None, client_socket=None):
    """Applies healing over time effect."""
    if combat_session:
        combat_session['status_effects'].append({
            "type": "hot",
            "target": target,
            "value": value,
            "end_time": time.time() + duration
        })
        if client_socket:
            client_socket.sendall(
                f"{target['name']} is blessed with a healing over time effect!\n".encode()
            )

def apply_stun(target, duration, combat_session=None, client_socket=None):
    """Applies stun effect."""
    target['is_stunned'] = True
    
    if combat_session:
        combat_session['status_effects'].append({
            "type": "stun",
            "target": target,
            "end_time": time.time() + duration
        })
        if client_socket:
            client_socket.sendall(f"{target['name']} is stunned!\n".encode())

def apply_silence(target, duration, combat_session=None, client_socket=None):
    """Applies silence effect (prevents skill/spell usage)."""
    target['is_silenced'] = True
    
    if combat_session:
        combat_session['status_effects'].append({
            "type": "silence",
            "target": target,
            "end_time": time.time() + duration
        })
        if client_socket:
            client_socket.sendall(f"{target['name']} is silenced!\n".encode())

# Dictionary mapping effect names to their handler functions
EFFECT_HANDLERS = {
    "damage": apply_damage,
    "heal": apply_heal,
    "buff": apply_buff,
    "debuff": apply_debuff,
    "dot": apply_dot,
    "hot": apply_hot,
    "stun": apply_stun,
    "silence": apply_silence
}

def apply_effect_to_target(effect_function, target, value, duration=0, **kwargs):
    """Applies an effect to a single target."""
    if duration == 0:
        effect_function(target, value, **kwargs)
    else:
        effect_function(target, value, duration, **kwargs)

def apply_effect(effect_name: str, targets: Any, value: int, duration: int = 0, **kwargs):
    """
    Applies an effect to specified targets using the EFFECT_HANDLERS dictionary.
    
    Args:
        effect_name: The name of the effect to apply
        targets: Single target or list of targets to apply the effect to
        value: The effect's primary value (e.g., damage amount)
        duration: Duration for temporary effects (in seconds)
        **kwargs: Additional arguments passed to the effect handler
    """
    if effect_name in EFFECT_HANDLERS:
        effect_function = EFFECT_HANDLERS[effect_name]
        if isinstance(targets, list):
            for target in targets:
                apply_effect_to_target(effect_function, target, value, duration, **kwargs)
        else:
            apply_effect_to_target(effect_function, targets, value, duration, **kwargs)
    else:
        logging.warning(f"Effect '{effect_name}' is not defined.")

def remove_expired_effects(combat_session):
    """Removes expired effects from the combat session."""
    current_time = time.time()
    active_effects = [effect for effect in combat_session['status_effects'] 
                     if current_time < effect['end_time']]
    
    expired_effects = [effect for effect in combat_session['status_effects'] 
                      if current_time >= effect['end_time']]
    
    # Clean up expired effects
    for effect in expired_effects:
        target = effect['target']
        if effect['type'] == 'stun':
            target['is_stunned'] = False
        elif effect['type'] == 'silence':
            target['is_silenced'] = False
        elif effect['type'] in ['buff', 'debuff']:
            target['stats'][effect['stat']] -= effect['value']
    
    combat_session['status_effects'] = active_effects
