import tkinter as tk
from tkinter import ttk, messagebox
import json
from base_tab import BaseTab

class ArmorTab(BaseTab):
    def __init__(self, parent, file_paths, stats):
        # Define equipment slots before calling parent's __init__
        self.equipment_slots = ["Head", "Neck", "Chest", "Waist", "Legs", "Feet", "Hands", "Ring"]
        self.TYPE_MAPPINGS = {
            "Armor": "armors",
            "Weapon": "weapons",
            "Item": "items",
            "Consumable": "consumables"
        }
        super().__init__(parent, file_paths, stats)

    def setup_ui(self):
        """Setup the armor tab UI elements."""
        # VNUM and basic fields
        self.armor_vnum_entry = self.create_labeled_entry(self, "VNUM:", 0, width=20)
        self.armor_name_entry = self.create_labeled_entry(self, "Name:", 1, width=50)
        self.armor_short_desc_entry = self.create_labeled_entry(self, "Short Description:", 2, width=50)
        self.armor_long_desc_entry = self.create_labeled_text(self, "Long Description:", 3, height=4, width=50)

        # Equipment Slot selection
        ttk.Label(self, text="Equipment Slot:").grid(column=0, row=4, padx=5, pady=5, sticky="W")
        self.armor_slot_var = tk.StringVar(value=self.equipment_slots[0])
        self.armor_slot_menu = ttk.OptionMenu(
            self, 
            self.armor_slot_var, 
            self.equipment_slots[0], 
            *self.equipment_slots
        )
        self.armor_slot_menu.grid(column=1, row=4, padx=5, pady=5, sticky="W")

        # Stats frame
        self.stat_vars, self.stat_entries = self.create_stats_frame(self)

        # Value field
        self.armor_value_entry = self.create_labeled_entry(self, "Value (Gold):", 6, width=20)

        # Light Source checkbox
        self.is_light_source_var = tk.BooleanVar()
        ttk.Checkbutton(
            self, 
            text="Is Light Source?", 
            variable=self.is_light_source_var
        ).grid(column=0, row=7, padx=5, pady=5, sticky="W")

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
        save_button = ttk.Button(button_frame, text="Save Armor", command=self.save_armor)
        save_button.grid(column=1, row=0, padx=5, pady=5)

        # Armor Listbox
        self.armor_listbox = tk.Listbox(self, height=10, width=50)
        self.armor_listbox.grid(column=0, row=10, columnspan=2, padx=5, pady=5)
        self.armor_listbox.bind("<Double-1>", self.edit_armor)
        self.update_armor_listbox()

    def save_armor(self):
        """Save armor data with validation."""
        vnum = self.armor_vnum_entry.get().strip()
        if not self.check_vnum(vnum):
            return

        item_name = self.armor_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter an armor name.")
            return

        # Collect field values
        armor_data = {
            "vnum": vnum,
            "name": item_name,
            "type": self.TYPE_MAPPINGS["Armor"],
            "slot": self.armor_slot_var.get(),
            "short_desc": self.armor_short_desc_entry.get().strip(),
            "long_desc": self.armor_long_desc_entry.get("1.0", "end-1c").strip(),
            "stats": self.collect_stats(),
            "is_light_source": self.is_light_source_var.get(),
            "value": self.get_integer_value("Value", self.armor_value_entry.get().strip()),
            "is_lore": self.is_lore_var.get(),
            "is_no_rent": self.is_no_rent_var.get()
        }

        # Save the data
        if self.save_to_json(armor_data):
            messagebox.showinfo("Success", "Armor saved successfully!")
            self.clear_fields()
            self.update_armor_listbox()

    def clear_fields(self):
        """Clear all input fields."""
        self.armor_vnum_entry.delete(0, "end")
        self.armor_name_entry.delete(0, "end")
        self.armor_short_desc_entry.delete(0, "end")
        self.armor_long_desc_entry.delete("1.0", "end")
        
        for stat in self.stat_vars:
            self.stat_vars[stat].set(False)
            self.stat_entries[stat].delete(0, "end")
            self.stat_entries[stat].configure(state="disabled")
            
        self.is_light_source_var.set(False)
        self.is_lore_var.set(False)
        self.is_no_rent_var.set(False)
        self.armor_value_entry.delete(0, "end")
        self.armor_slot_var.set(self.equipment_slots[0])

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

    def get_integer_value(self, field_name, value):
        """Convert and validate integer fields."""
        try:
            return int(value)
        except ValueError:
            messagebox.showerror("Error", f"{field_name} must be an integer.")
            raise ValueError(f"{field_name} must be an integer")

    def edit_armor(self, event):
        """Load selected armor for editing."""
        selected = self.armor_listbox.curselection()
        if not selected:
            return

        try:
            with open(self.get_file_path(), "r") as f:
                items = json.load(f)
                item = items[selected[0]]
                
                # Set current edit vnum
                self.current_edit_vnum = str(item["vnum"])
                
                # Load basic fields
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
                self.armor_slot_var.set(item.get("slot", self.equipment_slots[0]))

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

                self.is_light_source_var.set(item.get("is_light_source", False))
                self.is_lore_var.set(item.get("is_lore", False))
                self.is_no_rent_var.set(item.get("is_no_rent", False))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load armor: {str(e)}")

    def get_file_path(self):
        """Return the file path for armor data."""
        return self.file_paths["Armor"]

    def update_armor_listbox(self):
        """Update the armor listbox with current items."""
        self.armor_listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                items = json.load(f)
                for item in items:
                    self.armor_listbox.insert(tk.END, 
                        f"VNUM: {item['vnum']} - Name: {item['name']}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass


