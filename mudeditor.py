import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

class MudEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MUD Editor")
        self.geometry("1600x900")  # Increased size for better visibility
        self.resizable(True, True)  # Allow window resizing
        self.used_vnums = set()  # Track used VNUMs
        self.current_loaded_vnum = None  # Track the currently loaded VNUM
        self.current_item_type = None  # Track the current item type being edited

        # Ensure the game_data directory exists
        self.data_dir = "game_data"
        os.makedirs(self.data_dir, exist_ok=True)

        # Define paths for JSON files (now all in game_data)
        self.file_paths = {
            "Armor": os.path.join(self.data_dir, "armor.json"),
            "Weapon": os.path.join(self.data_dir, "weapons.json"),
            "Item": os.path.join(self.data_dir, "items.json"),
            "Consumable": os.path.join(self.data_dir, "consumables.json"),
            "Room": os.path.join(self.data_dir, "rooms.json"),
            "Mob": os.path.join(self.data_dir, "mobs.json"),
        }

        self.stats = [
            "HP", "SP", "AP", "Strength", "Tenacity", "Agility",
            "Intelligence", "Revel", "Defense"
        ]

        self.load_existing_vnums()  # Load existing VNUMs into used_vnums
        self.create_tabs()

    def load_existing_vnums(self):
        """
        Load all existing VNUMs from JSON files into used_vnums.
        """
        for item_type, file_path in self.file_paths.items():
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):  # Handle cases like armor, consumables, weapons
                            for item in data:
                                self.used_vnums.add(str(item["vnum"]))
                        elif isinstance(data, dict):  # Handle complex files like items.json
                            for category, items in data.items():
                                if isinstance(items, list):  # Ensure the value is a list
                                    for item in items:
                                        self.used_vnums.add(str(item["vnum"]))
                    except json.JSONDecodeError:
                        pass  # Handle empty or malformed JSON files silently


    def ensure_json_exists(self, file_path):
        """
        Ensure that the JSON file exists. If it doesn't, create an empty list and save it.
        """
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump([], f, indent=4)

    def save_to_json(self, file_path, data):
        """
        Save the data to a JSON file, ensuring the file exists first.
        """
        self.ensure_json_exists(file_path)  # Ensure the file exists

        # Load existing data, append the new data, and save
        with open(file_path, 'r') as f:
            try:
                items = json.load(f)
            except json.JSONDecodeError:
                items = []

        items.append(data)

        with open(file_path, 'w') as f:
            json.dump(items, f, indent=4)

    def check_vnum(self, vnum):
        """Check if a VNUM is already used."""
        # Ensure the file exists before checking
        file_path = self.file_paths[self.current_item_type]
        self.ensure_json_exists(file_path)  # Create an empty file if it doesn't exist

        # Now load the existing items and check for the VNUM
        with open(file_path, 'r') as f:
            try:
                items = json.load(f)
                for item in items:
                    if item['vnum'] == vnum:
                        messagebox.showerror("Error", f"VNUM {vnum} is already used. Please choose another.")
                        return False
            except json.JSONDecodeError:
                pass  # No items in the file yet

        return True

    def update_used_vnums(self):
        """
        Update the set of used VNUMs from all data files.
        """
        self.used_vnums.clear()
        for item_type, file_path in self.file_paths.items():
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    try:
                        items = json.load(f)
                        for item in items:
                            self.used_vnums.add(item['vnum'])
                    except json.JSONDecodeError:
                        pass

    def toggle_stat_entry(self, stat):
        """
        Show or hide stat entry box based on the checkbox.
        """
        if self.stat_vars[stat].get():
            self.stat_entries[stat].configure(state="normal")
        else:
            self.stat_entries[stat].delete(0, tk.END)
            self.stat_entries[stat].configure(state="disabled")

    def create_tabs(self):
        """
        Create all tabs in the editor.
        """
        tab_control = ttk.Notebook(self)

        self.create_armor_tab(tab_control)
        self.create_weapon_tab(tab_control)
        self.create_item_tab(tab_control)
        self.create_consumable_tab(tab_control)
        self.create_mob_tab(tab_control)
        self.create_room_tab(tab_control)

        tab_control.pack(expand=1, fill="both")

    def create_armor_tab(self, tab_control):
        """
        Create the Armor tab in the editor.
        """
        armor_tab = ttk.Frame(tab_control)
        tab_control.add(armor_tab, text="Armor")

        # VNUM, Name, Short and Long Description fields
        ttk.Label(armor_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5, sticky="W")
        self.armor_vnum_entry = ttk.Entry(armor_tab, width=20)
        self.armor_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(armor_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5, sticky="W")
        self.armor_name_entry = ttk.Entry(armor_tab, width=50)
        self.armor_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(armor_tab, text="Short Description:").grid(column=0, row=2, padx=5, pady=5, sticky="W")
        self.armor_short_desc_entry = ttk.Entry(armor_tab, width=50)
        self.armor_short_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        ttk.Label(armor_tab, text="Long Description:").grid(column=0, row=3, padx=5, pady=5, sticky="W")
        self.armor_long_desc_entry = tk.Text(armor_tab, height=4, width=50)
        self.armor_long_desc_entry.grid(column=1, row=3, padx=5, pady=5)

        # Equipment Slot selection
        ttk.Label(armor_tab, text="Equipment Slot:").grid(column=0, row=4, padx=5, pady=5, sticky="W")
        self.armor_slot_var = tk.StringVar()
        self.armor_slot_var.set("Head")  # Default value
        equipment_slots = ["Head", "Neck", "Chest", "Waist", "Legs", "Feet", "Hands", "Ring"]
        self.armor_slot_menu = ttk.OptionMenu(armor_tab, self.armor_slot_var, equipment_slots[0], *equipment_slots)
        self.armor_slot_menu.grid(column=1, row=4, padx=5, pady=5, sticky="W")

        # Stat checkboxes and entry boxes
        stat_frame = ttk.Frame(armor_tab)
        stat_frame.grid(column=0, row=5, columnspan=2, padx=5, pady=5)

        self.stat_vars = {}
        self.stat_entries = {}

        row = 0
        for stat in self.stats:
            var = tk.BooleanVar()
            self.stat_vars[stat] = var
            checkbox = ttk.Checkbutton(stat_frame, text=stat, variable=var, command=lambda s=stat: self.toggle_stat_entry(s))
            checkbox.grid(column=0, row=row, padx=5, pady=2, sticky="W")
            entry = ttk.Entry(stat_frame, width=10)
            entry.grid(column=1, row=row, padx=5, pady=2)
            entry.configure(state="disabled")
            self.stat_entries[stat] = entry
            row += 1

        # Value field
        ttk.Label(armor_tab, text="Value (Gold):").grid(column=0, row=6, padx=5, pady=5, sticky="W")
        self.armor_value_entry = ttk.Entry(armor_tab, width=20)
        self.armor_value_entry.grid(column=1, row=6, padx=5, pady=5)

        # Light Source checkbox
        self.is_light_source_var = tk.BooleanVar()
        ttk.Checkbutton(armor_tab, text="Is Light Source?", variable=self.is_light_source_var).grid(column=0, row=7, padx=5, pady=5, sticky="W")

        # Save Button
        save_button = ttk.Button(armor_tab, text="Save Armor", command=self.save_armor)
        save_button.grid(column=1, row=8, padx=5, pady=10)

        # Armor Listbox with double-click to re-edit
        self.armor_listbox = tk.Listbox(armor_tab, height=10, width=50)
        self.armor_listbox.grid(column=0, row=9, columnspan=2, padx=5, pady=5)
        self.armor_listbox.bind("<Double-1>", self.edit_armor)
        self.update_armor_listbox()

    def save_armor(self):
        """
        Save the armor to armor.json.
        """
        vnum = self.armor_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Armor"
        if not self.check_vnum(vnum):
            return

        item_name = self.armor_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter an armor name.")
            return

        short_desc = self.armor_short_desc_entry.get().strip()
        long_desc = self.armor_long_desc_entry.get("1.0", "end-1c").strip()

        # Get stat values from checkboxes and entries
        stats = {}
        for stat, var in self.stat_vars.items():
            if var.get():
                stat_value = self.stat_entries[stat].get().strip()
                if stat_value:  # Handle both +1, 1, and -1 cases
                    if stat_value.startswith('+'):
                        stat_value = stat_value[1:]
                    try:
                        stats[stat] = int(stat_value)
                    except ValueError:
                        messagebox.showerror("Error", f"Invalid stat value for {stat}.")
                        return

        is_light_source = self.is_light_source_var.get()

        value = self.armor_value_entry.get().strip()
        try:
            value = int(value)
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        slot = self.armor_slot_var.get()

        armor_data = {
            "vnum": vnum,
            "name": item_name,
            "type": "Armor",
            "slot": slot,
            "short_desc": short_desc,
            "long_desc": long_desc,
            "stats": stats,
            "is_light_source": is_light_source,
            "value": value,
        }

        file_path = self.file_paths["Armor"]
        self.save_to_json(file_path, armor_data)

        messagebox.showinfo("Success", "Armor saved successfully!")
        self.clear_armor_fields()
        self.update_armor_listbox()

    def clear_armor_fields(self):
        """
        Clear armor input fields after saving.
        """
        self.armor_vnum_entry.delete(0, "end")
        self.armor_name_entry.delete(0, "end")
        self.armor_short_desc_entry.delete(0, "end")
        self.armor_long_desc_entry.delete("1.0", "end")
        for stat in self.stat_vars:
            self.stat_vars[stat].set(False)
            self.stat_entries[stat].delete(0, "end")
            self.stat_entries[stat].configure(state="disabled")
        self.is_light_source_var.set(False)
        self.armor_value_entry.delete(0, "end")
        self.armor_slot_var.set("Head")  # Reset to default

    def update_armor_listbox(self):
        """
        Update the armor listbox with current items.
        """
        self.armor_listbox.delete(0, tk.END)
        file_path = self.file_paths["Armor"]
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    items = json.load(f)
                    for item in items:
                        display_text = f"VNUM: {item['vnum']} - Name: {item['name']}"
                        self.armor_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    pass

    def edit_armor(self, event):
        """
        Load selected armor into the input fields for editing.
        """
        selected = self.armor_listbox.curselection()
        if selected:
            index = selected[0]
            file_path = self.file_paths["Armor"]
            with open(file_path, "r") as f:
                items = json.load(f)
            item = items[index]
            self.armor_vnum_entry.delete(0, "end")
            self.armor_vnum_entry.insert(0, item["vnum"])
            self.armor_name_entry.delete(0, "end")
            self.armor_name_entry.insert(0, item["name"])
            self.armor_short_desc_entry.delete(0, "end")
            self.armor_short_desc_entry.insert(0, item["short_desc"])
            self.armor_long_desc_entry.delete("1.0", "end")
            self.armor_long_desc_entry.insert("1.0", item["long_desc"])
            self.armor_value_entry.delete(0, "end")
            self.armor_value_entry.insert(0, item["value"])
            self.armor_slot_var.set(item.get("slot", "Head"))

            # Load stats
            for stat in self.stat_vars:
                self.stat_vars[stat].set(False)
                self.stat_entries[stat].delete(0, "end")
                self.stat_entries[stat].configure(state="disabled")
            for stat, value in item["stats"].items():
                if stat in self.stat_vars:
                    self.stat_vars[stat].set(True)
                    self.stat_entries[stat].configure(state="normal")
                    self.stat_entries[stat].delete(0, "end")
                    self.stat_entries[stat].insert(0, value)

            self.is_light_source_var.set(item.get("is_light_source", False))

    def create_weapon_tab(self, tab_control):
        """
        Create the Weapon tab in the editor.
        """
        weapon_tab = ttk.Frame(tab_control)
        tab_control.add(weapon_tab, text="Weapons")

        ttk.Label(weapon_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.weapon_vnum_entry = ttk.Entry(weapon_tab, width=20)
        self.weapon_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(weapon_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.weapon_name_entry = ttk.Entry(weapon_tab, width=50)
        self.weapon_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(weapon_tab, text="Short Description:").grid(column=0, row=2, padx=5, pady=5)
        self.weapon_short_desc_entry = ttk.Entry(weapon_tab, width=50)
        self.weapon_short_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        ttk.Label(weapon_tab, text="Long Description:").grid(column=0, row=3, padx=5, pady=5)
        self.weapon_long_desc_entry = tk.Text(weapon_tab, height=4, width=50)
        self.weapon_long_desc_entry.grid(column=1, row=3, padx=5, pady=5)

        ttk.Label(weapon_tab, text="Min Damage:").grid(column=0, row=4, padx=5, pady=5)
        self.weapon_min_damage_entry = ttk.Entry(weapon_tab, width=20)
        self.weapon_min_damage_entry.grid(column=1, row=4, padx=5, pady=5)

        ttk.Label(weapon_tab, text="Max Damage:").grid(column=0, row=5, padx=5, pady=5)
        self.weapon_max_damage_entry = ttk.Entry(weapon_tab, width=20)
        self.weapon_max_damage_entry.grid(column=1, row=5, padx=5, pady=5)

        # Stat checkboxes and entry boxes
        stat_frame = ttk.Frame(weapon_tab)
        stat_frame.grid(column=0, row=6, columnspan=2, padx=5, pady=5)

        self.weapon_stat_vars = {}
        self.weapon_stat_entries = {}

        row = 0
        for stat in self.stats:
            var = tk.BooleanVar()
            self.weapon_stat_vars[stat] = var
            checkbox = ttk.Checkbutton(stat_frame, text=stat, variable=var, command=lambda s=stat: self.toggle_weapon_stat_entry(s))
            checkbox.grid(column=0, row=row, padx=5, pady=2, sticky="W")
            entry = ttk.Entry(stat_frame, width=10)
            entry.grid(column=1, row=row, padx=5, pady=2)
            entry.configure(state="disabled")
            self.weapon_stat_entries[stat] = entry
            row += 1

        # Value field
        ttk.Label(weapon_tab, text="Value (Gold):").grid(column=0, row=7, padx=5, pady=5, sticky="W")
        self.weapon_value_entry = ttk.Entry(weapon_tab, width=20)
        self.weapon_value_entry.grid(column=1, row=7, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(weapon_tab, text="Save Weapon", command=self.save_weapon)
        save_button.grid(column=1, row=8, padx=5, pady=10)

        # Weapon Listbox with double-click to re-edit
        self.weapon_listbox = tk.Listbox(weapon_tab, height=10, width=50)
        self.weapon_listbox.grid(column=0, row=9, columnspan=2, padx=5, pady=5)
        self.weapon_listbox.bind("<Double-1>", self.edit_weapon)
        self.update_weapon_listbox()

    def toggle_weapon_stat_entry(self, stat):
        """
        Show or hide stat entry box based on the checkbox.
        """
        if self.weapon_stat_vars[stat].get():
            self.weapon_stat_entries[stat].configure(state="normal")
        else:
            self.weapon_stat_entries[stat].delete(0, tk.END)
            self.weapon_stat_entries[stat].configure(state="disabled")

    def save_weapon(self):
        """
        Save the weapon to weapons.json.
        """
        vnum = self.weapon_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Weapon"
        if not self.check_vnum(vnum):
            return

        item_name = self.weapon_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter a weapon name.")
            return

        short_desc = self.weapon_short_desc_entry.get().strip()
        long_desc = self.weapon_long_desc_entry.get("1.0", "end-1c").strip()
        min_damage = self.weapon_min_damage_entry.get().strip()
        max_damage = self.weapon_max_damage_entry.get().strip()

        try:
            min_damage = int(min_damage)
            max_damage = int(max_damage)
        except ValueError:
            messagebox.showerror("Error", "Damage values must be integers.")
            return

        # Get stat values from checkboxes and entries
        stats = {}
        for stat, var in self.weapon_stat_vars.items():
            if var.get():
                stat_value = self.weapon_stat_entries[stat].get().strip()
                if stat_value:
                    if stat_value.startswith('+'):
                        stat_value = stat_value[1:]
                    try:
                        stats[stat] = int(stat_value)
                    except ValueError:
                        messagebox.showerror("Error", f"Invalid stat value for {stat}.")
                        return

        value = self.weapon_value_entry.get().strip()
        try:
            value = int(value)
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        weapon_data = {
            "vnum": vnum,
            "name": item_name,
            "type": "Weapon",
            "short_desc": short_desc,
            "long_desc": long_desc,
            "min_damage": min_damage,
            "max_damage": max_damage,
            "stats": stats,
            "value": value,
        }

        file_path = self.file_paths["Weapon"]
        self.save_to_json(file_path, weapon_data)

        messagebox.showinfo("Success", "Weapon saved successfully!")
        self.clear_weapon_fields()
        self.update_weapon_listbox()

    def clear_weapon_fields(self):
        """
        Clear weapon input fields after saving.
        """
        self.weapon_vnum_entry.delete(0, "end")
        self.weapon_name_entry.delete(0, "end")
        self.weapon_short_desc_entry.delete(0, "end")
        self.weapon_long_desc_entry.delete("1.0", "end")
        self.weapon_min_damage_entry.delete(0, "end")
        self.weapon_max_damage_entry.delete(0, "end")
        for stat in self.weapon_stat_vars:
            self.weapon_stat_vars[stat].set(False)
            self.weapon_stat_entries[stat].delete(0, "end")
            self.weapon_stat_entries[stat].configure(state="disabled")
        self.weapon_value_entry.delete(0, "end")

    def update_weapon_listbox(self):
        """
        Update the weapon listbox with current items.
        """
        self.weapon_listbox.delete(0, tk.END)
        file_path = self.file_paths["Weapon"]
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    items = json.load(f)
                    for item in items:
                        display_text = f"VNUM: {item['vnum']} - Name: {item['name']}"
                        self.weapon_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    pass

    def edit_weapon(self, event):
        """
        Load selected weapon into the input fields for editing.
        """
        selected = self.weapon_listbox.curselection()
        if selected:
            index = selected[0]
            file_path = self.file_paths["Weapon"]
            with open(file_path, "r") as f:
                items = json.load(f)
            item = items[index]
            self.weapon_vnum_entry.delete(0, "end")
            self.weapon_vnum_entry.insert(0, item["vnum"])
            self.weapon_name_entry.delete(0, "end")
            self.weapon_name_entry.insert(0, item["name"])
            self.weapon_short_desc_entry.delete(0, "end")
            self.weapon_short_desc_entry.insert(0, item["short_desc"])
            self.weapon_long_desc_entry.delete("1.0", "end")
            self.weapon_long_desc_entry.insert("1.0", item["long_desc"])
            self.weapon_min_damage_entry.delete(0, "end")
            self.weapon_min_damage_entry.insert(0, item["min_damage"])
            self.weapon_max_damage_entry.delete(0, "end")
            self.weapon_max_damage_entry.insert(0, item["max_damage"])
            self.weapon_value_entry.delete(0, "end")
            self.weapon_value_entry.insert(0, item["value"])

            # Load stats
            for stat in self.weapon_stat_vars:
                self.weapon_stat_vars[stat].set(False)
                self.weapon_stat_entries[stat].delete(0, "end")
                self.weapon_stat_entries[stat].configure(state="disabled")
            for stat, value in item["stats"].items():
                if stat in self.weapon_stat_vars:
                    self.weapon_stat_vars[stat].set(True)
                    self.weapon_stat_entries[stat].configure(state="normal")
                    self.weapon_stat_entries[stat].delete(0, "end")
                    self.weapon_stat_entries[stat].insert(0, value)

    # Similar methods can be created for items, consumables, rooms, and mobs.
    def create_item_tab(self, tab_control):
        """
        Create the Item tab in the editor.
        """
        item_tab = ttk.Frame(tab_control)
        tab_control.add(item_tab, text="Items")

        ttk.Label(item_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.item_vnum_entry = ttk.Entry(item_tab, width=20)
        self.item_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(item_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.item_name_entry = ttk.Entry(item_tab, width=50)
        self.item_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(item_tab, text="Short Description:").grid(column=0, row=2, padx=5, pady=5)
        self.item_short_desc_entry = ttk.Entry(item_tab, width=50)
        self.item_short_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        ttk.Label(item_tab, text="Long Description:").grid(column=0, row=3, padx=5, pady=5)
        self.item_long_desc_entry = tk.Text(item_tab, height=4, width=50)
        self.item_long_desc_entry.grid(column=1, row=3, padx=5, pady=5)

        ttk.Label(item_tab, text="Value:").grid(column=0, row=4, padx=5, pady=5)
        self.item_value_entry = ttk.Entry(item_tab, width=20)
        self.item_value_entry.grid(column=1, row=4, padx=5, pady=5)

        # Immobile Checkbox
        self.item_immobile_var = tk.BooleanVar()
        ttk.Checkbutton(item_tab, text="Immobile", variable=self.item_immobile_var).grid(column=0, row=5, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(item_tab, text="Save Item", command=self.save_item)
        save_button.grid(column=1, row=6, padx=5, pady=10)

        # Item Listbox with double-click to re-edit
        self.item_listbox = tk.Listbox(item_tab, height=10, width=50)
        self.item_listbox.grid(column=0, row=7, columnspan=2, padx=5, pady=5)
        self.item_listbox.bind("<Double-1>", self.edit_item)
        self.update_item_listbox()

    def save_item(self):
        """
        Save the item to items.json.
        """
        vnum = self.item_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Item"
        if not self.check_vnum(vnum):
            return

        item_name = self.item_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter an item name.")
            return

        short_desc = self.item_short_desc_entry.get().strip()
        long_desc = self.item_long_desc_entry.get("1.0", "end-1c").strip()
        value = self.item_value_entry.get().strip()
        try:
            value = int(value)
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        immobile = self.item_immobile_var.get()

        item_data = {
            "vnum": vnum,
            "name": item_name,
            "type": "Item",
            "short_desc": short_desc,
            "long_desc": long_desc,
            "value": value,
            "immobile": immobile,
        }

        file_path = self.file_paths["Item"]
        self.save_to_json(file_path, item_data)

        messagebox.showinfo("Success", "Item saved successfully!")
        self.clear_item_fields()
        self.update_item_listbox()

    def clear_item_fields(self):
        """
        Clear item input fields after saving.
        """
        self.item_vnum_entry.delete(0, "end")
        self.item_name_entry.delete(0, "end")
        self.item_short_desc_entry.delete(0, "end")
        self.item_long_desc_entry.delete("1.0", "end")
        self.item_value_entry.delete(0, "end")
        self.item_immobile_var.set(False)

def update_item_listbox(self):
    """
    Update the item listbox with current items.
    """
    self.item_listbox.delete(0, tk.END)
    file_path = self.file_paths["Item"]
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                # Since items.json is structured as a dictionary with categories
                if isinstance(data, dict) and "items" in data:
                    for item in data["items"]:
                        display_text = f"VNUM: {item['vnum']} - Name: {item['name']}"
                        self.item_listbox.insert(tk.END, display_text)
            except json.JSONDecodeError:
                pass




def edit_item(self, event):
    """
    Load selected item into the input fields for editing.
    """
    selected = self.item_listbox.curselection()
    if selected:
        index = selected[0]
        file_path = self.file_paths["Item"]
        with open(file_path, "r") as f:
            data = json.load(f)
        
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            item = items[index]
            
            self.item_vnum_entry.delete(0, "end")
            self.item_vnum_entry.insert(0, item["vnum"])
            self.item_name_entry.delete(0, "end")
            self.item_name_entry.insert(0, item["name"])
            self.item_short_desc_entry.delete(0, "end")
            self.item_short_desc_entry.insert(0, item["short_desc"])
            self.item_long_desc_entry.delete("1.0", "end")
            self.item_long_desc_entry.insert("1.0", item["long_desc"])
            self.item_value_entry.delete(0, "end")
            self.item_value_entry.insert(0, item["value"])
            self.item_immobile_var.set(item.get("immobile", False))

    def create_consumable_tab(self, tab_control):
        """
        Create the Consumable tab in the editor.
        """
        consumable_tab = ttk.Frame(tab_control)
        tab_control.add(consumable_tab, text="Consumables")

        ttk.Label(consumable_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.consumable_vnum_entry = ttk.Entry(consumable_tab, width=20)
        self.consumable_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(consumable_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.consumable_name_entry = ttk.Entry(consumable_tab, width=50)
        self.consumable_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(consumable_tab, text="Short Description:").grid(column=0, row=2, padx=5, pady=5)
        self.consumable_short_desc_entry = ttk.Entry(consumable_tab, width=50)
        self.consumable_short_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        ttk.Label(consumable_tab, text="Long Description:").grid(column=0, row=3, padx=5, pady=5)
        self.consumable_long_desc_entry = tk.Text(consumable_tab, height=4, width=50)
        self.consumable_long_desc_entry.grid(column=1, row=3, padx=5, pady=5)

        # Effect selection
        ttk.Label(consumable_tab, text="Effect:").grid(column=0, row=4, padx=5, pady=5)
        self.consumable_effect_var = tk.StringVar()
        self.consumable_effect_var.set("Heal")
        effects = ["Heal", "Mana", "Stamina", "Buff", "Debuff"]
        effect_menu = ttk.OptionMenu(consumable_tab, self.consumable_effect_var, effects[0], *effects)
        effect_menu.grid(column=1, row=4, padx=5, pady=5)

        ttk.Label(consumable_tab, text="Effect Value:").grid(column=0, row=5, padx=5, pady=5)
        self.consumable_effect_value_entry = ttk.Entry(consumable_tab, width=20)
        self.consumable_effect_value_entry.grid(column=1, row=5, padx=5, pady=5)

        ttk.Label(consumable_tab, text="Value (Gold):").grid(column=0, row=6, padx=5, pady=5)
        self.consumable_value_entry = ttk.Entry(consumable_tab, width=20)
        self.consumable_value_entry.grid(column=1, row=6, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(consumable_tab, text="Save Consumable", command=self.save_consumable)
        save_button.grid(column=1, row=7, padx=5, pady=10)

        # Consumable Listbox
        self.consumable_listbox = tk.Listbox(consumable_tab, height=10, width=50)
        self.consumable_listbox.grid(column=0, row=8, columnspan=2, padx=5, pady=5)
        self.consumable_listbox.bind("<Double-1>", self.edit_consumable)
        self.update_consumable_listbox()

    def save_consumable(self):
        """
        Save the consumable to consumables.json.
        """
        vnum = self.consumable_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Consumable"
        if not self.check_vnum(vnum):
            return

        item_name = self.consumable_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter a consumable name.")
            return

        short_desc = self.consumable_short_desc_entry.get().strip()
        long_desc = self.consumable_long_desc_entry.get("1.0", "end-1c").strip()
        effect = self.consumable_effect_var.get()
        effect_value = self.consumable_effect_value_entry.get().strip()
        try:
            effect_value = int(effect_value)
        except ValueError:
            messagebox.showerror("Error", "Effect Value must be an integer.")
            return

        value = self.consumable_value_entry.get().strip()
        try:
            value = int(value)
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        consumable_data = {
            "vnum": vnum,
            "name": item_name,
            "type": "Consumable",
            "short_desc": short_desc,
            "long_desc": long_desc,
            "effect": effect,
            "effect_value": effect_value,
            "value": value,
        }

        file_path = self.file_paths["Consumable"]
        self.save_to_json(file_path, consumable_data)

        messagebox.showinfo("Success", "Consumable saved successfully!")
        self.clear_consumable_fields()
        self.update_consumable_listbox()

    def clear_consumable_fields(self):
        """
        Clear consumable input fields after saving.
        """
        self.consumable_vnum_entry.delete(0, "end")
        self.consumable_name_entry.delete(0, "end")
        self.consumable_short_desc_entry.delete(0, "end")
        self.consumable_long_desc_entry.delete("1.0", "end")
        self.consumable_effect_var.set("Heal")
        self.consumable_effect_value_entry.delete(0, "end")
        self.consumable_value_entry.delete(0, "end")

    def update_consumable_listbox(self):
        """
        Update the consumable listbox with current items.
        """
        self.consumable_listbox.delete(0, tk.END)
        file_path = self.file_paths["Consumable"]
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    items = json.load(f)
                    for item in items:
                        display_text = f"VNUM: {item['vnum']} - Name: {item['name']}"
                        self.consumable_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    pass

    def edit_consumable(self, event):
        """
        Load selected consumable into the input fields for editing.
        """
        selected = self.consumable_listbox.curselection()
        if selected:
            index = selected[0]
            file_path = self.file_paths["Consumable"]
            with open(file_path, "r") as f:
                items = json.load(f)
            item = items[index]
            self.consumable_vnum_entry.delete(0, "end")
            self.consumable_vnum_entry.insert(0, item["vnum"])
            self.consumable_name_entry.delete(0, "end")
            self.consumable_name_entry.insert(0, item["name"])
            self.consumable_short_desc_entry.delete(0, "end")
            self.consumable_short_desc_entry.insert(0, item["short_desc"])
            self.consumable_long_desc_entry.delete("1.0", "end")
            self.consumable_long_desc_entry.insert("1.0", item["long_desc"])
            self.consumable_effect_var.set(item["effect"])
            self.consumable_effect_value_entry.delete(0, "end")
            self.consumable_effect_value_entry.insert(0, item["effect_value"])
            self.consumable_value_entry.delete(0, "end")
            self.consumable_value_entry.insert(0, item["value"])
    def create_room_tab(self, tab_control):
        """
        Create the Room tab in the editor.
        """
        room_tab = ttk.Frame(tab_control)
        tab_control.add(room_tab, text="Rooms")

        ttk.Label(room_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.room_vnum_entry = ttk.Entry(room_tab, width=20)
        self.room_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(room_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.room_name_entry = ttk.Entry(room_tab, width=50)
        self.room_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(room_tab, text="Description:").grid(column=0, row=2, padx=5, pady=5)
        self.room_desc_entry = tk.Text(room_tab, height=4, width=50)
        self.room_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        # Exits
        exits_frame = ttk.Frame(room_tab)
        exits_frame.grid(column=0, row=3, columnspan=2, padx=5, pady=5)

        self.exits_entries = {}

        directions = ["north", "south", "east", "west", "up", "down"]
        row = 0
        for direction in directions:
            ttk.Label(exits_frame, text=f"{direction.capitalize()} Exit VNUM:").grid(column=0, row=row, padx=5, pady=2, sticky="W")
            entry = ttk.Entry(exits_frame, width=20)
            entry.grid(column=1, row=row, padx=5, pady=2)
            self.exits_entries[direction] = entry
            row += 1

        # Save Button
        save_button = ttk.Button(room_tab, text="Save Room", command=self.save_room)
        save_button.grid(column=1, row=4, padx=5, pady=10)

        # Room Listbox
        self.room_listbox = tk.Listbox(room_tab, height=10, width=50)
        self.room_listbox.grid(column=0, row=5, columnspan=2, padx=5, pady=5)
        self.room_listbox.bind("<Double-1>", self.edit_room)
        self.update_room_listbox()

    def save_room(self):
        """
        Save the room to rooms.json.
        """
        vnum = self.room_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Room"
        if not self.check_vnum(vnum):
            return

        room_name = self.room_name_entry.get().strip()
        if not room_name:
            messagebox.showerror("Error", "Please enter a room name.")
            return

        description = self.room_desc_entry.get("1.0", "end-1c").strip()

        # Get exits
        exits = {}
        for direction, entry in self.exits_entries.items():
            exit_vnum = entry.get().strip()
            if exit_vnum:
                exits[direction] = exit_vnum

        room_data = {
            "vnum": vnum,
            "name": room_name,
            "description": description,
            "exits": exits,
        }

        file_path = self.file_paths["Room"]
        self.save_to_json(file_path, room_data)

        messagebox.showinfo("Success", "Room saved successfully!")
        self.clear_room_fields()
        self.update_room_listbox()

    def clear_room_fields(self):
        """
        Clear room input fields after saving.
        """
        self.room_vnum_entry.delete(0, "end")
        self.room_name_entry.delete(0, "end")
        self.room_desc_entry.delete("1.0", "end")
        for entry in self.exits_entries.values():
            entry.delete(0, "end")

    def update_room_listbox(self):
        """
        Update the room listbox with current items.
        """
        self.room_listbox.delete(0, tk.END)
        file_path = self.file_paths["Room"]
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    rooms = json.load(f)
                    for room in rooms:
                        display_text = f"VNUM: {room['vnum']} - Name: {room['name']}"
                        self.room_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    pass

    def edit_room(self, event):
        """
        Load selected room into the input fields for editing.
        """
        selected = self.room_listbox.curselection()
        if selected:
            index = selected[0]
            file_path = self.file_paths["Room"]
            with open(file_path, "r") as f:
                rooms = json.load(f)
            room = rooms[index]
            self.room_vnum_entry.delete(0, "end")
            self.room_vnum_entry.insert(0, room["vnum"])
            self.room_name_entry.delete(0, "end")
            self.room_name_entry.insert(0, room["name"])
            self.room_desc_entry.delete("1.0", "end")
            self.room_desc_entry.insert("1.0", room["description"])
            for direction in self.exits_entries:
                self.exits_entries[direction].delete(0, "end")
            for direction, exit_vnum in room.get("exits", {}).items():
                if direction in self.exits_entries:
                    self.exits_entries[direction].insert(0, exit_vnum)
    def create_mob_tab(self, tab_control):
        """
        Create the Mob tab in the editor.
        """
        mob_tab = ttk.Frame(tab_control)
        tab_control.add(mob_tab, text="Mobs")

        ttk.Label(mob_tab, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.mob_vnum_entry = ttk.Entry(mob_tab, width=20)
        self.mob_vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(mob_tab, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.mob_name_entry = ttk.Entry(mob_tab, width=50)
        self.mob_name_entry.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(mob_tab, text="Description:").grid(column=0, row=2, padx=5, pady=5)
        self.mob_desc_entry = tk.Text(mob_tab, height=4, width=50)
        self.mob_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        # Stats
        stat_frame = ttk.Frame(mob_tab)
        stat_frame.grid(column=0, row=3, columnspan=2, padx=5, pady=5)

        self.mob_stat_entries = {}

        row = 0
        for stat in self.stats:
            ttk.Label(stat_frame, text=stat + ":").grid(column=0, row=row, padx=5, pady=2, sticky="W")
            entry = ttk.Entry(stat_frame, width=10)
            entry.grid(column=1, row=row, padx=5, pady=2)
            self.mob_stat_entries[stat] = entry
            row += 1

        # Aggressive Checkbox
        self.mob_aggressive_var = tk.BooleanVar()
        ttk.Checkbutton(mob_tab, text="Is Aggressive?", variable=self.mob_aggressive_var).grid(column=0, row=4, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(mob_tab, text="Save Mob", command=self.save_mob)
        save_button.grid(column=1, row=5, padx=5, pady=10)

        # Mob Listbox
        self.mob_listbox = tk.Listbox(mob_tab, height=10, width=50)
        self.mob_listbox.grid(column=0, row=6, columnspan=2, padx=5, pady=5)
        self.mob_listbox.bind("<Double-1>", self.edit_mob)
        self.update_mob_listbox()

    def save_mob(self):
        """
        Save the mob to mobs.json.
        """
        vnum = self.mob_vnum_entry.get().strip()
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return
        self.current_item_type = "Mob"
        if not self.check_vnum(vnum):
            return

        mob_name = self.mob_name_entry.get().strip()
        if not mob_name:
            messagebox.showerror("Error", "Please enter a mob name.")
            return

        description = self.mob_desc_entry.get("1.0", "end-1c").strip()

        # Get stats
        stats = {}
        for stat, entry in self.mob_stat_entries.items():
            stat_value = entry.get().strip()
            try:
                stats[stat] = int(stat_value)
            except ValueError:
                messagebox.showerror("Error", f"{stat} must be an integer.")
                return

        is_aggressive = self.mob_aggressive_var.get()

        mob_data = {
            "vnum": vnum,
            "name": mob_name,
            "description": description,
            "stats": stats,
            "is_aggressive": is_aggressive,
        }

        file_path = self.file_paths["Mob"]
        self.save_to_json(file_path, mob_data)

        messagebox.showinfo("Success", "Mob saved successfully!")
        self.clear_mob_fields()
        self.update_mob_listbox()

    def clear_mob_fields(self):
        """
        Clear mob input fields after saving.
        """
        self.mob_vnum_entry.delete(0, "end")
        self.mob_name_entry.delete(0, "end")
        self.mob_desc_entry.delete("1.0", "end")
        for entry in self.mob_stat_entries.values():
            entry.delete(0, "end")
        self.mob_aggressive_var.set(False)

    def update_mob_listbox(self):
        """
        Update the mob listbox with current items.
        """
        self.mob_listbox.delete(0, tk.END)
        file_path = self.file_paths["Mob"]
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    mobs = json.load(f)
                    for mob in mobs:
                        display_text = f"VNUM: {mob['vnum']} - Name: {mob['name']}"
                        self.mob_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    pass

    def edit_mob(self, event):
        """
        Load selected mob into the input fields for editing.
        """
        selected = self.mob_listbox.curselection()
        if selected:
            index = selected[0]
            file_path = self.file_paths["Mob"]
            with open(file_path, "r") as f:
                mobs = json.load(f)
            mob = mobs[index]
            self.mob_vnum_entry.delete(0, "end")
            self.mob_vnum_entry.insert(0, mob["vnum"])
            self.mob_name_entry.delete(0, "end")
            self.mob_name_entry.insert(0, mob["name"])
            self.mob_desc_entry.delete("1.0", "end")
            self.mob_desc_entry.insert("1.0", mob["description"])
            for stat, value in mob["stats"].items():
                self.mob_stat_entries[stat].delete(0, "end")
                self.mob_stat_entries[stat].insert(0, value)
            self.mob_aggressive_var.set(mob.get("is_aggressive", False))

    
if __name__ == "__main__":
    editor = MudEditor()
    editor.mainloop()
