import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

class BaseTab(ttk.Frame):
    def __init__(self, parent, file_paths, stats):
        super().__init__(parent)
        self.file_paths = file_paths
        self.stats = stats
        self.used_vnums = set()
        self.current_edit_vnum = None
        
        # Add variables for LORE and NO-RENT flags
        self.is_lore_var = tk.BooleanVar()
        self.is_no_rent_var = tk.BooleanVar()
        
        self.load_existing_vnums()
        self.setup_ui()

    def load_existing_vnums(self):
        """Load all existing VNUMs from JSON files."""
        current_file = self.get_file_path()
        if os.path.exists(current_file):
            with open(current_file, "r") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            self.used_vnums.add(str(item["vnum"]))
                except json.JSONDecodeError:
                    pass

    def create_labeled_entry(self, parent, label_text, row, width=None):
        """Create a labeled entry widget."""
        ttk.Label(parent, text=label_text).grid(column=0, row=row, padx=5, pady=5, sticky="W")
        entry = ttk.Entry(parent, width=width) if width else ttk.Entry(parent)
        entry.grid(column=1, row=row, padx=5, pady=5)
        return entry

    def create_labeled_text(self, parent, label_text, row, height=None, width=None):
        """Create a labeled text widget."""
        ttk.Label(parent, text=label_text).grid(column=0, row=row, padx=5, pady=5, sticky="W")
        text = tk.Text(parent, height=height, width=width)
        text.grid(column=1, row=row, padx=5, pady=5)
        return text

    def create_flags_frame(self, parent, row):
        """Create a frame for item flags (LORE and NO-RENT)."""
        # Only create flags for non-mob and non-room tabs
        tab_type = str(self).lower()
        if 'room' in tab_type or 'mob' in tab_type:
            return None

        flags_frame = ttk.Frame(parent)
        flags_frame.grid(column=0, row=row, columnspan=2, padx=5, pady=5, sticky="W")

        # LORE checkbox
        ttk.Checkbutton(
            flags_frame,
            text="LORE (Limit One Per Character)",
            variable=self.is_lore_var
        ).pack(side=tk.LEFT, padx=5)

        # NO-RENT checkbox
        ttk.Checkbutton(
            flags_frame,
            text="NO-RENT (Removed After Logout)",
            variable=self.is_no_rent_var
        ).pack(side=tk.LEFT, padx=5)

        return flags_frame

    def create_stats_frame(self, parent):
        """Create a frame with stat checkboxes and entries."""
        stat_frame = ttk.Frame(parent)
        stat_frame.grid(column=0, row=5, columnspan=2, padx=5, pady=5)

        stat_vars = {}
        stat_entries = {}

        for row, stat in enumerate(self.stats):
            var = tk.BooleanVar()
            stat_vars[stat] = var
            checkbox = ttk.Checkbutton(
                stat_frame,
                text=stat,
                variable=var,
                command=lambda s=stat: self.toggle_stat_entry(s, stat_vars, stat_entries)
            )
            checkbox.grid(column=0, row=row, padx=5, pady=2, sticky="W")

            entry = ttk.Entry(stat_frame, width=10)
            entry.grid(column=1, row=row, padx=5, pady=2)
            entry.configure(state="disabled")
            stat_entries[stat] = entry

        return stat_vars, stat_entries

    def toggle_stat_entry(self, stat, stat_vars, stat_entries):
        """Toggle stat entry field based on checkbox."""
        if stat_vars[stat].get():
            stat_entries[stat].configure(state="normal")
        else:
            stat_entries[stat].delete(0, tk.END)
            stat_entries[stat].configure(state="disabled")

    def check_vnum(self, vnum):
        """Check if a VNUM is already used, allowing reuse of current edit VNUM."""
        if not vnum:
            messagebox.showerror("Error", "Please enter a VNUM.")
            return False
        if vnum in self.used_vnums and vnum != self.current_edit_vnum:
            messagebox.showerror("Error", f"VNUM {vnum} is already used. Please choose another.")
            return False
        return True

    def save_to_json(self, data):
        """Save data to JSON file with update support."""
        try:
            file_path = self.get_file_path()
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)

            with open(file_path, 'r') as f:
                try:
                    items = json.load(f)
                except json.JSONDecodeError:
                    items = []

            # Ensure items is a list
            if not isinstance(items, list):
                items = []

            # Only add flags for non-mob and non-room items
            tab_type = str(self).lower()
            if 'room' not in tab_type and 'mob' not in tab_type:
                data['is_lore'] = self.is_lore_var.get()
                data['is_no_rent'] = self.is_no_rent_var.get()

            # Handle updating existing item
            if self.current_edit_vnum:
                updated = False
                for i, item in enumerate(items):
                    if str(item['vnum']) == str(self.current_edit_vnum):
                        items[i] = data
                        updated = True
                        break
                if not updated:
                    items.append(data)
            else:
                items.append(data)
                self.used_vnums.add(str(data['vnum']))

            with open(file_path, 'w') as f:
                json.dump(items, f, indent=4)

            self.current_edit_vnum = None
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {str(e)}")
            return False

    def load_item_for_edit(self, item_data):
        """Load an item's data into the editor fields for editing."""
        if item_data:
            # Only load flags for non-mob and non-room items
            tab_type = str(self).lower()
            if 'room' not in tab_type and 'mob' not in tab_type:
                self.is_lore_var.set(item_data.get('is_lore', False))
                self.is_no_rent_var.set(item_data.get('is_no_rent', False))
            self.current_edit_vnum = str(item_data.get('vnum'))
        else:
            self.is_lore_var.set(False)
            self.is_no_rent_var.set(False)
            self.current_edit_vnum = None

    def create_reset_button(self, parent, row):
        """Create a reset button for clearing fields."""
        reset_button = ttk.Button(parent, text="Reset", command=self.reset_fields)
        reset_button.grid(column=0, row=row, padx=5, pady=5, sticky="W")
        return reset_button

    def reset_fields(self):
        """Reset all fields and current edit state."""
        self.current_edit_vnum = None
        tab_type = str(self).lower()
        if 'room' not in tab_type and 'mob' not in tab_type:
            self.is_lore_var.set(False)
            self.is_no_rent_var.set(False)
        self.clear_fields()

    def clear_fields(self):
        """To be implemented by child classes."""
        raise NotImplementedError("Child classes must implement clear_fields")

    def setup_ui(self):
        """To be implemented by child classes."""
        raise NotImplementedError("Child classes must implement setup_ui")

    def get_file_path(self):
        """To be implemented by child classes."""
        raise NotImplementedError("Child classes must implement get_file_path")