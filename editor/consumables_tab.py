import tkinter as tk
from tkinter import ttk, messagebox
import json
from base_tab import BaseTab

class ConsumableTab(BaseTab):
    def __init__(self, parent, file_paths, stats):
        # Define class attributes before calling parent's __init__
        self.consumable_types = ["Food", "Drink", "Potion", "Scroll", "Key"]
        self.effect_types = ["Heal", "Restore SP", "Restore AP", "Buff", "Teleport"]
        self.TYPE_MAPPINGS = {
            "Armor": "armors",
            "Weapon": "weapons",
            "Item": "items",
            "Consumable": "consumables"
        }
        super().__init__(parent, file_paths, stats)

    def setup_ui(self):
        """Setup the consumable tab UI elements."""
        # Basic Fields
        self.consumable_vnum_entry = self.create_labeled_entry(self, "VNUM:", 0, width=20)
        self.consumable_name_entry = self.create_labeled_entry(self, "Name:", 1, width=50)
        self.consumable_short_desc_entry = self.create_labeled_entry(self, "Short Description:", 2, width=50)
        self.consumable_long_desc_entry = self.create_labeled_text(self, "Long Description:", 3, height=4, width=50)

        # Consumable Type Selection
        ttk.Label(self, text="Consumable Type:").grid(column=0, row=4, padx=5, pady=5, sticky="W")
        self.consumable_type_var = tk.StringVar(value=self.consumable_types[0])
        self.consumable_type_menu = ttk.OptionMenu(
            self,
            self.consumable_type_var,
            self.consumable_types[0],
            *self.consumable_types
        )
        self.consumable_type_menu.grid(column=1, row=4, padx=5, pady=5, sticky="W")

        # Effect Frame
        effect_frame = ttk.LabelFrame(self, text="Effect Properties")
        effect_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Effect Type Selection
        ttk.Label(effect_frame, text="Effect Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.effect_type_var = tk.StringVar(value=self.effect_types[0])
        self.effect_type_menu = ttk.OptionMenu(
            effect_frame,
            self.effect_type_var,
            self.effect_types[0],
            *self.effect_types
        )
        self.effect_type_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Effect Value
        ttk.Label(effect_frame, text="Effect Value:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.effect_value_entry = ttk.Entry(effect_frame, width=10)
        self.effect_value_entry.grid(row=1, column=1, padx=5, pady=5)

        # Duration
        ttk.Label(effect_frame, text="Duration (seconds):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.duration_entry = ttk.Entry(effect_frame, width=10)
        self.duration_entry.grid(row=2, column=1, padx=5, pady=5)

        # Item Properties Frame
        props_frame = ttk.LabelFrame(self, text="Item Properties")
        props_frame.grid(row=6, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Uses
        ttk.Label(props_frame, text="Number of Uses:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.uses_entry = ttk.Entry(props_frame, width=10)
        self.uses_entry.grid(row=0, column=1, padx=5, pady=5)

        # Value
        ttk.Label(props_frame, text="Value (Gold):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.consumable_value_entry = ttk.Entry(props_frame, width=10)
        self.consumable_value_entry.grid(row=1, column=1, padx=5, pady=5)

        # LORE and NO-RENT flags
        flags_frame = ttk.Frame(self)
        flags_frame.grid(column=0, row=7, columnspan=2, padx=5, pady=5, sticky="W")

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
        button_frame.grid(column=0, row=8, columnspan=2, padx=5, pady=5)

        # Reset Button
        self.create_reset_button(button_frame, 0).grid(column=0, row=0, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(button_frame, text="Save Consumable", command=self.save_consumable)
        save_button.grid(column=1, row=0, padx=5, pady=5)

        # Consumable Listbox
        self.consumable_listbox = tk.Listbox(self, height=10, width=50)
        self.consumable_listbox.grid(column=0, row=9, columnspan=2, padx=5, pady=5)
        self.consumable_listbox.bind("<Double-1>", self.edit_consumable)
        self.update_consumable_listbox()

    def get_file_path(self):
        """Return the file path for consumable data."""
        return self.file_paths["Consumable"]

    def save_consumable(self):
        """Save consumable data with validation."""
        # Validate required fields
        vnum = self.consumable_vnum_entry.get().strip()
        if not self.check_vnum(vnum):
            return

        consumable_name = self.consumable_name_entry.get().strip()
        if not consumable_name:
            messagebox.showerror("Error", "Please enter a consumable name.")
            return

        # Validate effect value
        try:
            effect_value = int(self.effect_value_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Effect value must be an integer.")
            return

        # Validate duration (if provided)
        duration = self.duration_entry.get().strip()
        if duration:
            try:
                duration = int(duration)
            except ValueError:
                messagebox.showerror("Error", "Duration must be an integer.")
                return
        else:
            duration = 0

        # Validate uses
        uses = self.uses_entry.get().strip()
        try:
            uses = int(uses) if uses else 1
        except ValueError:
            messagebox.showerror("Error", "Number of uses must be an integer.")
            return

        # Validate value
        try:
            value = int(self.consumable_value_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        # Collect consumable data
        consumable_data = {
            "vnum": vnum,
            "name": consumable_name,
            "type": self.TYPE_MAPPINGS["Consumable"],
            "consumable_type": self.consumable_type_var.get(),
            "short_desc": self.consumable_short_desc_entry.get().strip(),
            "long_desc": self.consumable_long_desc_entry.get("1.0", "end-1c").strip(),
            "effect_type": self.effect_type_var.get(),
            "effect_value": effect_value,
            "duration": duration,
            "uses": uses,
            "value": value,
            "is_lore": self.is_lore_var.get(),
            "is_no_rent": self.is_no_rent_var.get()
        }

        # Save the data
        if self.save_to_json(consumable_data):
            messagebox.showinfo("Success", "Consumable saved successfully!")
            self.clear_fields()
            self.update_consumable_listbox()

    def clear_fields(self):
        """Clear all input fields."""
        self.consumable_vnum_entry.delete(0, "end")
        self.consumable_name_entry.delete(0, "end")
        self.consumable_short_desc_entry.delete(0, "end")
        self.consumable_long_desc_entry.delete("1.0", "end")
        self.effect_value_entry.delete(0, "end")
        self.duration_entry.delete(0, "end")
        self.uses_entry.delete(0, "end")
        self.consumable_value_entry.delete(0, "end")
        self.consumable_type_var.set(self.consumable_types[0])
        self.effect_type_var.set(self.effect_types[0])
        self.is_lore_var.set(False)
        self.is_no_rent_var.set(False)

    def update_consumable_listbox(self):
        """Update the listbox with current consumables."""
        self.consumable_listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                items = json.load(f)
                for item in items:
                    self.consumable_listbox.insert(tk.END, 
                        f"VNUM: {item['vnum']} - Name: {item['name']}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def edit_consumable(self, event):
        """Load selected consumable for editing."""
        selected = self.consumable_listbox.curselection()
        if not selected:
            return

        try:
            with open(self.get_file_path(), "r") as f:
                items = json.load(f)
                item = items[selected[0]]

                # Set current edit vnum
                self.current_edit_vnum = str(item["vnum"])
                
                # Load basic fields
                self.consumable_vnum_entry.delete(0, "end")
                self.consumable_vnum_entry.insert(0, item["vnum"])
                self.consumable_name_entry.delete(0, "end")
                self.consumable_name_entry.insert(0, item["name"])
                self.consumable_short_desc_entry.delete(0, "end")
                self.consumable_short_desc_entry.insert(0, item["short_desc"])
                self.consumable_long_desc_entry.delete("1.0", "end")
                self.consumable_long_desc_entry.insert("1.0", item["long_desc"])
                
                # Load specific fields
                self.consumable_type_var.set(item.get("consumable_type", self.consumable_types[0]))
                self.effect_type_var.set(item.get("effect_type", self.effect_types[0]))
                
                self.effect_value_entry.delete(0, "end")
                self.effect_value_entry.insert(0, item.get("effect_value", ""))
                
                self.duration_entry.delete(0, "end")
                self.duration_entry.insert(0, item.get("duration", ""))
                
                self.uses_entry.delete(0, "end")
                self.uses_entry.insert(0, item.get("uses", "1"))
                
                self.consumable_value_entry.delete(0, "end")
                self.consumable_value_entry.insert(0, item.get("value", ""))
                
                # Load flags
                self.is_lore_var.set(item.get("is_lore", False))
                self.is_no_rent_var.set(item.get("is_no_rent", False))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load consumable: {str(e)}")