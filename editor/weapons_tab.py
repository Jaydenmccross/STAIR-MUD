import tkinter as tk
from tkinter import ttk, messagebox
import json
from base_tab import BaseTab

class WeaponTab(BaseTab):
    def __init__(self, parent, file_paths, stats):
        # Define class attributes before calling parent's __init__
        self.weapon_types = ["Sword", "Axe", "Spear", "Dagger", "Bow", "Staff", "Wand"]
        self.TYPE_MAPPINGS = {
            "Armor": "armors",
            "Weapon": "weapons",
            "Item": "items",
            "Consumable": "consumables"
        }
        super().__init__(parent, file_paths, stats)

    def setup_ui(self):
        """Setup the weapon tab UI elements."""
        # VNUM, Name, and Descriptions
        self.weapon_vnum_entry = self.create_labeled_entry(self, "VNUM:", 0, width=20)
        self.weapon_name_entry = self.create_labeled_entry(self, "Name:", 1, width=50)
        self.weapon_short_desc_entry = self.create_labeled_entry(self, "Short Description:", 2, width=50)
        self.weapon_long_desc_entry = self.create_labeled_text(self, "Long Description:", 3, height=4, width=50)

        # Weapon Type Selection
        ttk.Label(self, text="Weapon Type:").grid(column=0, row=4, padx=5, pady=5, sticky="W")
        self.weapon_type_var = tk.StringVar(value=self.weapon_types[0])
        self.weapon_type_menu = ttk.OptionMenu(
            self,
            self.weapon_type_var,
            self.weapon_types[0],
            *self.weapon_types
        )
        self.weapon_type_menu.grid(column=1, row=4, padx=5, pady=5, sticky="W")

        # Damage Fields Frame
        damage_frame = ttk.LabelFrame(self, text="Damage")
        damage_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Min Damage
        ttk.Label(damage_frame, text="Min Damage:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.min_damage_entry = ttk.Entry(damage_frame, width=10)
        self.min_damage_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Max Damage
        ttk.Label(damage_frame, text="Max Damage:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.max_damage_entry = ttk.Entry(damage_frame, width=10)
        self.max_damage_entry.grid(row=1, column=1, padx=5, pady=5)

        # Stats Frame
        self.stat_vars, self.stat_entries = self.create_stats_frame(self)

        # Value Field
        self.weapon_value_entry = self.create_labeled_entry(self, "Value (Gold):", 7, width=20)

        # LORE and NO-RENT flags
        flags_frame = ttk.Frame(self)
        flags_frame.grid(column=0, row=8, columnspan=2, padx=5, pady=5, sticky="W")

        ttk.Checkbutton(
            flags_frame,
            text="LORE (Limit One Per Character)",
            variable=self.is_lore_var
        ).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(
            flags_frame,
            text="NO-RENT (Removed After Logout)",
            variable=self.is_no_rent_var
        ).pack(side=tk.LEFT, padx=5)

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.grid(column=0, row=9, columnspan=2, padx=5, pady=5)

        # Reset Button
        self.create_reset_button(button_frame, 0).grid(column=0, row=0, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(button_frame, text="Save Weapon", command=self.save_weapon)
        save_button.grid(column=1, row=0, padx=5, pady=5)

        # Weapon Listbox
        self.weapon_listbox = tk.Listbox(self, height=10, width=50)
        self.weapon_listbox.grid(column=0, row=10, columnspan=2, padx=5, pady=5)
        self.weapon_listbox.bind("<Double-1>", self.edit_weapon)
        self.update_weapon_listbox()

    def get_file_path(self):
        """Return the file path for weapon data."""
        return self.file_paths["Weapon"]

    def save_weapon(self):
        """Save weapon data with validation."""
        # Validate required fields
        vnum = self.weapon_vnum_entry.get().strip()
        if not self.check_vnum(vnum):
            return

        weapon_name = self.weapon_name_entry.get().strip()
        if not weapon_name:
            messagebox.showerror("Error", "Please enter a weapon name.")
            return

        try:
            min_damage = int(self.min_damage_entry.get().strip())
            max_damage = int(self.max_damage_entry.get().strip())
            if min_damage > max_damage:
                messagebox.showerror("Error", "Minimum damage cannot be greater than maximum damage.")
                return
        except ValueError:
            messagebox.showerror("Error", "Damage values must be integers.")
            return

        value = self.weapon_value_entry.get().strip()
        try:
            value = int(value)
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        # Collect weapon data
        weapon_data = {
            "vnum": vnum,
            "name": weapon_name,
            "type": self.TYPE_MAPPINGS["Weapon"],
            "weapon_type": self.weapon_type_var.get(),
            "short_desc": self.weapon_short_desc_entry.get().strip(),
            "long_desc": self.weapon_long_desc_entry.get("1.0", "end-1c").strip(),
            "min_damage": min_damage,
            "max_damage": max_damage,
            "stats": self.collect_stats(),
            "value": value,
            "is_lore": self.is_lore_var.get(),
            "is_no_rent": self.is_no_rent_var.get()
        }

        # Save the data
        if self.save_to_json(weapon_data):
            messagebox.showinfo("Success", "Weapon saved successfully!")
            self.clear_fields()
            self.update_weapon_listbox()

    def clear_fields(self):
        """Clear all input fields."""
        self.weapon_vnum_entry.delete(0, "end")
        self.weapon_name_entry.delete(0, "end")
        self.weapon_short_desc_entry.delete(0, "end")
        self.weapon_long_desc_entry.delete("1.0", "end")
        self.min_damage_entry.delete(0, "end")
        self.max_damage_entry.delete(0, "end")
        self.weapon_value_entry.delete(0, "end")
        self.weapon_type_var.set(self.weapon_types[0])
        self.is_lore_var.set(False)
        self.is_no_rent_var.set(False)
        
        for stat in self.stat_vars:
            self.stat_vars[stat].set(False)
            self.stat_entries[stat].delete(0, "end")
            self.stat_entries[stat].configure(state="disabled")

    def collect_stats(self):
        """Collect and validate stats from the UI."""
        stats = {}
        for stat, var in self.stat_vars.items():
            if var.get():
                stat_value = self.stat_entries[stat].get().strip()
                if stat_value:
                    if stat_value.startswith('+'):
                        stat_value = stat_value[1:]
                    try:
                        stats[stat] = int(stat_value)
                    except ValueError:
                        messagebox.showerror("Error", f"Invalid stat value for {stat}.")
                        raise ValueError(f"Invalid stat value for {stat}")
        return stats

    def update_weapon_listbox(self):
        """Update the weapon listbox with current weapons."""
        self.weapon_listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                items = json.load(f)
                for item in items:
                    self.weapon_listbox.insert(tk.END, 
                        f"VNUM: {item['vnum']} - Name: {item['name']}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def edit_weapon(self, event):
        """Load selected weapon for editing."""
        selected = self.weapon_listbox.curselection()
        if not selected:
            return

        try:
            with open(self.get_file_path(), "r") as f:
                items = json.load(f)
                item = items[selected[0]]
                
                # Set current edit vnum
                self.current_edit_vnum = str(item["vnum"])
                
                # Load basic fields
                self.weapon_vnum_entry.delete(0, "end")
                self.weapon_vnum_entry.insert(0, item["vnum"])
                self.weapon_name_entry.delete(0, "end")
                self.weapon_name_entry.insert(0, item["name"])
                self.weapon_short_desc_entry.delete(0, "end")
                self.weapon_short_desc_entry.insert(0, item["short_desc"])
                self.weapon_long_desc_entry.delete("1.0", "end")
                self.weapon_long_desc_entry.insert("1.0", item["long_desc"])
                
                # Load damage values
                self.min_damage_entry.delete(0, "end")
                self.min_damage_entry.insert(0, item.get("min_damage", ""))
                self.max_damage_entry.delete(0, "end")
                self.max_damage_entry.insert(0, item.get("max_damage", ""))
                
                # Load value
                self.weapon_value_entry.delete(0, "end")
                self.weapon_value_entry.insert(0, item.get("value", ""))
                
                # Load weapon type
                self.weapon_type_var.set(item.get("weapon_type", self.weapon_types[0]))

                # Load flags
                self.is_lore_var.set(item.get("is_lore", False))
                self.is_no_rent_var.set(item.get("is_no_rent", False))

                # Load stats
                for stat in self.stat_vars:
                    self.stat_vars[stat].set(False)
                    self.stat_entries[stat].delete(0, "end")
                    self.stat_entries[stat].configure(state="disabled")
                
                for stat, value in item.get("stats", {}).items():
                    if stat in self.stat_vars:
                        self.stat_vars[stat].set(True)
                        self.stat_entries[stat].configure(state="normal")
                        self.stat_entries[stat].delete(0, "end")
                        self.stat_entries[stat].insert(0, value)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load weapon: {str(e)}")
