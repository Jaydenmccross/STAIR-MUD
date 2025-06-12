import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from base_tab import BaseTab

class MobTab(BaseTab):
    def __init__(self, parent, file_paths, mob_stats):
        super().__init__(parent, file_paths, mob_stats)
        self.setup_ui()
        
    def get_file_path(self):
        """Return the file path for mob data."""
        return self.file_paths["Mob"]

    def setup_ui(self):
        """Setup the mob tab UI elements."""
        self.create_widgets()
        self.update_listbox()

    def create_widgets(self):
        """Create all widgets for the mob tab."""
        # Basic Info Frame
        basic_frame = ttk.LabelFrame(self, text="Basic Information")
        basic_frame.grid(column=0, row=0, padx=5, pady=5, sticky="ew")

        # VNUM field
        ttk.Label(basic_frame, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.vnum_entry = ttk.Entry(basic_frame, width=20)
        self.vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        # Name field
        ttk.Label(basic_frame, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.name_entry = ttk.Entry(basic_frame, width=50)
        self.name_entry.grid(column=1, row=1, padx=5, pady=5)

        # Short Description field
        ttk.Label(basic_frame, text="Short Description:").grid(column=0, row=2, padx=5, pady=5)
        self.short_desc_entry = ttk.Entry(basic_frame, width=50)
        self.short_desc_entry.grid(column=1, row=2, padx=5, pady=5)

        # Description field
        ttk.Label(basic_frame, text="Description:").grid(column=0, row=3, padx=5, pady=5)
        self.desc_entry = tk.Text(basic_frame, height=4, width=50)
        self.desc_entry.grid(column=1, row=3, padx=5, pady=5)

        # Create notebook for different settings
        settings_notebook = ttk.Notebook(self)
        settings_notebook.grid(column=0, row=1, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Add tabs to notebook
        stats_frame = self.create_stats_frame(settings_notebook)
        combat_frame = self.create_combat_frame(settings_notebook)
        loot_frame = self.create_loot_frame(settings_notebook)

        settings_notebook.add(stats_frame, text="Stats")
        settings_notebook.add(combat_frame, text="Combat")
        settings_notebook.add(loot_frame, text="Loot")

        # Save Button
        save_button = ttk.Button(self, text="Save Mob", command=self.save)
        save_button.grid(column=0, row=2, columnspan=2, pady=10)

        # Mob Listbox with Scrollbar
        self.listbox = tk.Listbox(self, height=10, width=50)
        self.listbox.grid(column=0, row=3, columnspan=2, padx=5, pady=5)
        self.listbox.bind("<Double-1>", self.on_select)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(column=2, row=3, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

    def create_stats_frame(self, parent):
        """Create the stats frame."""
        frame = ttk.LabelFrame(parent, text="Base Stats")
        frame.grid_columnconfigure(1, weight=1)

        # Create entries for each stat
        self.stat_entries = {}
        for idx, stat in enumerate(self.stats):
            ttk.Label(frame, text=f"{stat}:").grid(column=0, row=idx, padx=5, pady=2)
            entry = ttk.Entry(frame, width=10)
            entry.grid(column=1, row=idx, padx=5, pady=2)
            if stat in ['HP', 'Max_HP']:
                entry.insert(0, "40")  # Higher default HP
            elif stat in ['Ferocity', 'Resilience', 'Evasiveness']:
                entry.insert(0, "3")   # Default combat stats
            else:
                entry.insert(0, "0")   # Default for other stats
            self.stat_entries[stat] = entry

        # Experience and Gold rewards
        ttk.Label(frame, text="Experience:").grid(column=0, row=len(self.stats), padx=5, pady=2)
        self.exp_entry = ttk.Entry(frame, width=10)
        self.exp_entry.grid(column=1, row=len(self.stats), padx=5, pady=2)
        self.exp_entry.insert(0, "10")

        ttk.Label(frame, text="Gold:").grid(column=0, row=len(self.stats) + 1, padx=5, pady=2)
        self.gold_entry = ttk.Entry(frame, width=10)
        self.gold_entry.grid(column=1, row=len(self.stats) + 1, padx=5, pady=2)
        self.gold_entry.insert(0, "5")

        return frame

    def create_combat_frame(self, parent):
        """Create the combat settings frame."""
        frame = ttk.LabelFrame(parent, text="Combat Settings")
        frame.grid_columnconfigure(1, weight=1)

        # Aggression Settings
        ttk.Label(frame, text="Aggression:").grid(column=0, row=0, padx=5, pady=5)
        self.aggression_var = tk.StringVar(value="NEUTRAL")
        aggression_types = ["NEUTRAL", "AGGRESSIVE", "PASSIVE"]
        aggression_menu = ttk.OptionMenu(
            frame, 
            self.aggression_var, 
            "NEUTRAL", 
            *aggression_types
        )
        aggression_menu.grid(column=1, row=0, padx=5, pady=5, sticky="w")

        # Flee Settings
        ttk.Label(frame, text="Flee at HP%:").grid(column=0, row=1, padx=5, pady=5)
        self.flee_threshold_var = tk.StringVar(value="20")
        flee_entry = ttk.Entry(frame, textvariable=self.flee_threshold_var, width=10)
        flee_entry.grid(column=1, row=1, padx=5, pady=5, sticky="w")

        # Call for Help
        ttk.Label(frame, text="Call for Help:").grid(column=0, row=2, padx=5, pady=5)
        self.call_help_var = tk.BooleanVar(value=False)
        help_checkbox = ttk.Checkbutton(frame, variable=self.call_help_var)
        help_checkbox.grid(column=1, row=2, padx=5, pady=5, sticky="w")

        return frame

    def create_loot_frame(self, parent):
        """Create the loot settings frame."""
        frame = ttk.LabelFrame(parent, text="Loot Configuration")
        frame.grid_columnconfigure(1, weight=1)

        # Add text widget for loot entries
        self.loot_text = tk.Text(frame, height=8, width=40)
        self.loot_text.pack(padx=5, pady=5)

        # Helper text for loot format
        helper_text = (
            "Format: type:vnum:quantity:dropchance\n"
            "Example: a:1:1:75 (armor vnum 1, qty 1, 75% drop)\n"
            "Types: a=armor, w=weapon, i=item, c=consumable\n"
            "One item per line"
        )
        helper_label = ttk.Label(
            frame,
            text=helper_text,
            justify=tk.LEFT,
            font=('TkDefaultFont', 8, 'italic')
        )
        helper_label.pack(padx=5, pady=2)

        return frame

    def clear_fields(self):
        """Clear all input fields."""
        self.vnum_entry.delete(0, "end")
        self.name_entry.delete(0, "end")
        self.short_desc_entry.delete(0, "end")
        self.desc_entry.delete("1.0", "end")
        
        # Clear stat entries
        for stat, entry in self.stat_entries.items():
            entry.delete(0, "end")
            if stat in ['HP', 'Max_HP']:
                entry.insert(0, "40")
            elif stat in ['Ferocity', 'Resilience', 'Evasiveness']:
                entry.insert(0, "3")
            else:
                entry.insert(0, "0")
        
        # Reset exp and gold to defaults
        self.exp_entry.delete(0, "end")
        self.exp_entry.insert(0, "10")
        self.gold_entry.delete(0, "end")
        self.gold_entry.insert(0, "5")

        # Reset combat settings
        self.aggression_var.set("NEUTRAL")
        self.flee_threshold_var.set("20")
        self.call_help_var.set(False)
        
        # Clear loot configuration
        self.loot_text.delete("1.0", "end")

    def save(self):
        """Save the mob data."""
        try:
            # Validate basic fields
            vnum = self.vnum_entry.get().strip()
            if not vnum:
                messagebox.showerror("Error", "Please enter a VNUM.")
                return

            # Validate numeric fields
            try:
                exp = int(self.exp_entry.get())
                gold = int(self.gold_entry.get())
                flee_threshold = int(self.flee_threshold_var.get())
            except ValueError:
                messagebox.showerror("Error", "Numeric values must be valid integers.")
                return

            # Get stats
            stats = {}
            for stat, entry in self.stat_entries.items():
                try:
                    value = int(entry.get().strip())
                    if value < 0:
                        messagebox.showerror("Error", f"{stat} cannot be negative.")
                        return
                    stats[stat] = value
                except ValueError:
                    messagebox.showerror("Error", f"Invalid value for {stat}")
                    return

            # Parse loot configuration
            loot_pool = []
            loot_text = self.loot_text.get("1.0", "end-1c").strip()
            if loot_text:
                for line in loot_text.split('\n'):
                    if line.strip():
                        try:
                            type_code, vnum, quantity, drop_rate = line.strip().split(':')
                            type_mapping = {
                                'a': 'armors',
                                'w': 'weapons',
                                'i': 'items',
                                'c': 'consumables'
                            }
                            loot_pool.append({
                                'type': type_mapping.get(type_code.lower(), 'items'),
                                'vnum': vnum,
                                'quantity': int(quantity),
                                'drop_rate': float(drop_rate)
                            })
                        except ValueError:
                            messagebox.showerror("Error", f"Invalid loot entry format: {line}")
                            return

            # Build mob data structure
            mob_data = {
                "vnum": vnum,
                "name": self.name_entry.get().strip(),
                "short_desc": self.short_desc_entry.get().strip(),
                "description": self.desc_entry.get("1.0", "end-1c").strip(),
                "stats": stats,
                "combat": {
                    "aggression": self.aggression_var.get(),
                    "flee_threshold": flee_threshold,
                    "call_for_help": self.call_help_var.get()
                },
                "experience": exp,
                "gold": gold,
                "loot_pool": loot_pool
            }

            # Save to file
            try:
                with open(self.get_file_path(), 'r') as f:
                    mobs = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                mobs = []

            # Update or add mob
            found = False
            for i, mob in enumerate(mobs):
                if str(mob.get('vnum')) == str(vnum):
                    mobs[i] = mob_data
                    found = True
                    break
            if not found:
                mobs.append(mob_data)

            with open(self.get_file_path(), 'w') as f:
                json.dump(mobs, f, indent=4)

            messagebox.showinfo("Success", f"Mob '{mob_data['name']}' saved successfully!")
            self.clear_fields()
            self.update_listbox()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save mob: {str(e)}")
            logging.error(f"Error saving mob: {str(e)}")

    def on_select(self, event):
        """Handle mob selection from listbox."""
        selection = self.listbox.curselection()
        if not selection:
            return

        try:
            with open(self.get_file_path(), 'r') as f:
                mobs = json.load(f)
            
            selected_mob = mobs[selection[0]]
            if not selected_mob:
                raise ValueError("No mob data found at selected index")
            
            # Clear current fields
            self.clear_fields()

            # Load basic info
            self.vnum_entry.insert(0, selected_mob.get('vnum', ''))
            self.name_entry.insert(0, selected_mob.get('name', ''))
            self.short_desc_entry.insert(0, selected_mob.get('short_desc', ''))
            self.desc_entry.insert("1.0", selected_mob.get('description', ''))

            # Load stats
            stats = selected_mob.get('stats', {})
            for stat, entry in self.stat_entries.items():
                if stat in stats:
                    entry.delete(0, "end")
                    entry.insert(0, str(stats[stat]))

            # Load experience and gold
            self.exp_entry.delete(0, "end")
            self.exp_entry.insert(0, str(selected_mob.get('experience', 10)))
            self.gold_entry.delete(0, "end")
            self.gold_entry.insert(0, str(selected_mob.get('gold', 5)))

            # Load combat settings
            combat = selected_mob.get('combat', {})
            self.aggression_var.set(combat.get('aggression', 'NEUTRAL'))
            self.flee_threshold_var.set(str(combat.get('flee_threshold', 20)))
            self.call_help_var.set(combat.get('call_for_help', False))

            # Load loot configuration
            self.loot_text.delete("1.0", "end")
            for loot in selected_mob.get('loot_pool', []):
                type_code = {'armors': 'a', 'weapons': 'w', 'items': 'i', 'consumables': 'c'}.get(loot['type'], 'i')
                loot_line = f"{type_code}:{loot['vnum']}:{loot['quantity']}:{loot['drop_rate']}\n"
                self.loot_text.insert("end", loot_line)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mob data: {str(e)}")
            logging.error(f"Error loading mob: {str(e)}", exc_info=True)

    def update_listbox(self):
        """Update the mob listbox with current mobs."""
        self.listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                mobs = json.load(f)
                for mob in mobs:
                    display_text = f"VNUM: {mob['vnum']} - Name: {mob['name']}"
                    self.listbox.insert(tk.END, display_text)
        except (FileNotFoundError, json.JSONDecodeError):
            pass