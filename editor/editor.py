import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedStyle
import os
import sys
from base_tab import BaseTab

# Add the Mud_Project directory to Python's path
mud_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(mud_project_dir)

# Import the tab classes - use direct imports since we're in the editor directory
from armor_tab import ArmorTab
from weapons_tab import WeaponTab
from consumables_tab import ConsumableTab
from rooms_tab import RoomTab
from mobs_tab import MobTab
from items_tab import ItemTab
from containers_tab import ContainerTab

class MudEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MUD Editor")
        self.geometry("1600x900")
        self.resizable(True, True)

        # Apply the theme
        self.style = ThemedStyle(self)
        self.style.set_theme("black")

        # Define consistent stats lists
        self.character_stats = [
            "HP", "Max_HP", "AP", "Max_AP", "SP", "Max_SP",
            "Strength", "Tenacity", "Agility", "Intelligence",
            "Revel", "Defense"
        ]
        
        self.mob_stats = [
            "HP", "Max_HP", "AP", "Max_AP", "SP", "Max_SP",
            "Ferocity", "Resilience", "Evasiveness"
        ]

        # Setup data directory and file paths
        self.setup_data_directory()
        
        # Create tab control
        self.tab_control = ttk.Notebook(self)
        
        # Initialize tabs
        self.init_tabs()
        
        # Pack the tab control
        self.tab_control.pack(expand=1, fill="both")

    def setup_data_directory(self):
        """Setup data directory and file paths."""
        # Use the game_data directory at the Mud_Project level
        self.data_dir = os.path.join(mud_project_dir, 'game_data')
        
        # Define file paths
        self.file_paths = {
            "Armor": os.path.join(self.data_dir, "armor.json"),
            "Weapon": os.path.join(self.data_dir, "weapons.json"),
            "Item": os.path.join(self.data_dir, "items.json"),
            "Consumable": os.path.join(self.data_dir, "consumables.json"),
            "Room": os.path.join(self.data_dir, "rooms.json"),
            "Mob": os.path.join(self.data_dir, "mobs.json"),
            "Container": os.path.join(self.data_dir, "containers.json")
        }

        # Ensure game_data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # Ensure all JSON files exist
        for file_path in self.file_paths.values():
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)  # Initialize all files with an empty list

    def init_tabs(self):
        """Initialize all editor tabs."""
        # Create instances of each tab
        self.armor_tab = ArmorTab(self.tab_control, self.file_paths, self.character_stats)
        self.weapon_tab = WeaponTab(self.tab_control, self.file_paths, self.character_stats)
        self.consumable_tab = ConsumableTab(self.tab_control, self.file_paths, self.character_stats)
        self.room_tab = RoomTab(self.tab_control, self.file_paths)
        self.mob_tab = MobTab(self.tab_control, self.file_paths, self.mob_stats)
        self.item_tab = ItemTab(self.tab_control, self.file_paths, self.character_stats)
        self.container_tab = ContainerTab(self.tab_control, self.file_paths)

        # Add tabs to the notebook
        self.tab_control.add(self.armor_tab, text="Armors")
        self.tab_control.add(self.weapon_tab, text="Weapons")
        self.tab_control.add(self.consumable_tab, text="Consumables")
        self.tab_control.add(self.room_tab, text="Rooms")
        self.tab_control.add(self.mob_tab, text="Mobs")
        self.tab_control.add(self.item_tab, text="Items")
        self.tab_control.add(self.container_tab, text="Containers")

if __name__ == "__main__":
    editor = MudEditor()
    editor.mainloop()
