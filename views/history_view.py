import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
from typing import List
from models.database_models import TrackerHistory

logger = logging.getLogger(__name__)

class HistoryView:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.setup_gui()
    
    # ===== GUI SETUP METHODS =====
    
    def setup_gui(self):
        """Setup enhanced history tab GUI"""
        self.tab = ttk.Frame(self.parent)
        
        # Stats dashboard at the top
        self.setup_stats_dashboard()
        
        # Controls frame with enhanced filtering
        controls_frame = ttk.LabelFrame(self.tab, text="Controls & Filters", padding=10)
        controls_frame.pack(fill='x', padx=5, pady=5)
        
        # Top row - main controls
        top_controls = ttk.Frame(controls_frame)
        top_controls.pack(fill='x', pady=(0, 10))
        
        ttk.Button(top_controls, text="🔄 Refresh", 
                command=self.refresh_history).pack(side='left', padx=(0, 10))
        
        ttk.Button(top_controls, text="⭐ Show Reliable",
                command=self.show_reliable).pack(side='left', padx=(0, 10))
        
        ttk.Button(top_controls, text="❤️ Show Favorites",
                command=self.show_favorites).pack(side='left', padx=(0, 10))
        
        ttk.Button(top_controls, text="🧹 Clear History",
                command=self.clear_history).pack(side='left')
        
        # Bottom row - filters
        filter_frame = ttk.Frame(controls_frame)
        filter_frame.pack(fill='x')
        
        ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=(0, 5))
        
        self.filter_var = tk.StringVar()
        self.filter_combo = ttk.Combobox(filter_frame, 
                                    textvariable=self.filter_var,
                                    values=["All", "Working Only", "Dead Only", "High Reliability (>90%)", "Medium Reliability (70-90%)", "Low Reliability (<70%)"],
                                    state="readonly",
                                    width=20)
        self.filter_combo.set("All")
        self.filter_combo.pack(side='left', padx=(0, 10))
        self.filter_combo.bind('<<ComboboxSelected>>', self.apply_filter)
        
        ttk.Label(filter_frame, text="Limit:").pack(side='left', padx=(20, 5))
        
        self.limit_var = tk.StringVar(value="50")
        self.limit_combo = ttk.Combobox(filter_frame,
                                    textvariable=self.limit_var,
                                    values=["25", "50", "100", "250", "500", "All"],
                                    state="readonly",
                                    width=10)
        self.limit_combo.pack(side='left', padx=(0, 10))
        self.limit_combo.bind('<<ComboboxSelected>>', self.refresh_history)
        
        # Search box - USE REGULAR TK ENTRY INSTEAD OF TTK FOR BETTER THEMING
        ttk.Label(filter_frame, text="Search:").pack(side='left', padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(filter_frame, textvariable=self.search_var, width=20,  # Changed to tk.Entry
                                   bg="white", fg="black", insertbackground="black")  # Default light mode colors
        self.search_entry.pack(side='left', padx=(0, 5))
        self.search_entry.bind('<KeyRelease>', self.apply_search)
        
        ttk.Button(filter_frame, text="🔍", 
                command=self.apply_search, width=3).pack(side='left')
        
        # Enhanced history table
        columns = ('URL', 'Status', 'Response Time', 'Last Checked', 'Success Rate', 'Checks', 'Type')
        self.tree = ttk.Treeview(self.tab, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.tree.heading('URL', text='URL')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Response Time', text='Response Time')
        self.tree.heading('Last Checked', text='Last Checked')
        self.tree.heading('Success Rate', text='Success Rate')
        self.tree.heading('Checks', text='Checks')
        self.tree.heading('Type', text='Type')
        
        self.tree.column('URL', width=280, anchor='w')
        self.tree.column('Status', width=80, anchor='center')
        self.tree.column('Response Time', width=100, anchor='center')
        self.tree.column('Last Checked', width=140, anchor='center')
        self.tree.column('Success Rate', width=100, anchor='center')
        self.tree.column('Checks', width=60, anchor='center')
        self.tree.column('Type', width=80, anchor='center')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(self.tab, orient='vertical', command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(self.tab, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack everything
        self.tree.pack(side='top', fill='both', expand=True, padx=5, pady=5)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Enhanced bindings
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)
        
        # Context menu
        self.context_menu = tk.Menu(self.tab, tearoff=0)
        self.context_menu.add_command(label="Add to Favorites", command=self.add_selected_to_favorites)
        self.context_menu.add_command(label="Copy URL", command=self.copy_selected_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Validate Again", command=self.validate_selected)
        
        # Collect all labels for theming
        self._label_widgets = []
        self._collect_labels(self.tab)
        
        self.refresh_history()
    
    def setup_stats_dashboard(self):
        """Setup statistics dashboard"""
        stats_frame = ttk.LabelFrame(self.tab, text="Statistics Dashboard", padding=10)
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x')
        
        # Total trackers
        self.total_label = tk.Label(stats_grid, text="Total: 0", font=("Arial", 10, "bold"))
        self.total_label.grid(row=0, column=0, padx=10, pady=2, sticky='w')
        
        # Working trackers
        self.working_label = tk.Label(stats_grid, text="Working: 0", font=("Arial", 10, "bold"), fg="green")
        self.working_label.grid(row=0, column=1, padx=10, pady=2, sticky='w')
        
        # Dead trackers
        self.dead_label = tk.Label(stats_grid, text="Dead: 0", font=("Arial", 10, "bold"), fg="red")
        self.dead_label.grid(row=0, column=2, padx=10, pady=2, sticky='w')
        
        # Success rate
        self.success_label = tk.Label(stats_grid, text="Avg Success: 0%", font=("Arial", 10, "bold"))
        self.success_label.grid(row=0, column=3, padx=10, pady=2, sticky='w')
        
        # Reliability breakdown
        self.reliability_label = tk.Label(stats_grid, text="High Rel: 0", font=("Arial", 9))
        self.reliability_label.grid(row=1, column=0, padx=10, pady=2, sticky='w')
        
        self.medium_rel_label = tk.Label(stats_grid, text="Med Rel: 0", font=("Arial", 9))
        self.medium_rel_label.grid(row=1, column=1, padx=10, pady=2, sticky='w')
        
        self.low_rel_label = tk.Label(stats_grid, text="Low Rel: 0", font=("Arial", 9))
        self.low_rel_label.grid(row=1, column=2, padx=10, pady=2, sticky='w')
    
    # ===== SIMPLIFIED THEMING METHODS =====
    
    def apply_theme(self, bg_color, fg_color, text_bg, text_fg):
        """Apply theme to history tab widgets - SIMPLIFIED AND FOCUSED"""
        try:
            # Get dark mode state from main view
            is_dark_mode = getattr(self.controller.main_view, 'is_dark_mode', False)
            
            if is_dark_mode:
                # DARK MODE - Direct and simple approach
                self._apply_dark_theme(bg_color, fg_color)
            else:
                # LIGHT MODE
                self._apply_light_theme(bg_color, fg_color, text_bg)
            
            # Theme all labels
            self._theme_all_labels(bg_color, fg_color, is_dark_mode)
            
            # Theme context menu
            self._theme_context_menu(bg_color, fg_color, is_dark_mode)
            
        except Exception as e:
            logger.debug(f"Could not theme history view: {e}")
    
    def _apply_dark_theme(self, bg_color, fg_color):
        """Apply dark theme - FOCUSED ON SEARCH BAR"""
        dark_bg = "#2a2a2a"
        dark_fg = "#e8e8e8"
        dark_select = "#404040"
        
        # SEARCH BAR - Most important fix
        if hasattr(self, 'search_entry') and self.search_entry.winfo_exists():
            self.search_entry.configure(
                bg=dark_bg,
                fg=dark_fg,
                insertbackground=dark_fg,  # Cursor color
                selectbackground=dark_select,
                selectforeground=dark_fg,
                relief="flat"
            )
        
        # ComboBoxes
        for combo in [self.filter_combo, self.limit_combo]:
            if combo and combo.winfo_exists():
                try:
                    combo.configure(
                        background=dark_bg,
                        foreground=dark_fg
                    )
                except:
                    pass  # If ttk combobox doesn't support direct styling
    
    def _apply_light_theme(self, bg_color, fg_color, text_bg):
        """Apply light theme"""
        if hasattr(self, 'search_entry') and self.search_entry.winfo_exists():
            self.search_entry.configure(
                bg=text_bg,
                fg=fg_color,
                insertbackground=fg_color,
                selectbackground="#e0e0e0",
                selectforeground=fg_color,
                relief="sunken"
            )
        
        # ComboBoxes
        for combo in [self.filter_combo, self.limit_combo]:
            if combo and combo.winfo_exists():
                try:
                    combo.configure(
                        background=text_bg,
                        foreground=fg_color
                    )
                except:
                    pass
    
    def _theme_all_labels(self, bg_color, fg_color, is_dark_mode):
        """Theme all labels in the history tab"""
        # Apply to collected labels
        for label in self._label_widgets:
            if label and label.winfo_exists():
                try:
                    if is_dark_mode:
                        if label in [self.total_label, self.working_label, self.dead_label, self.success_label]:
                            label.configure(bg=bg_color, fg=fg_color, font=("Arial", 10, "bold"))
                        elif label in [self.reliability_label, self.medium_rel_label, self.low_rel_label]:
                            label.configure(bg=bg_color, fg="#cccccc", font=("Arial", 9))
                        else:
                            label.configure(bg=bg_color, fg=fg_color)
                    else:
                        label.configure(bg=bg_color, fg=fg_color)
                except Exception as e:
                    logger.debug(f"Could not theme label: {e}")
        
        # Apply recursive theming to catch any missed labels
        self._theme_all_labels_recursive(self.tab, bg_color, fg_color)
    
    def _theme_all_labels_recursive(self, parent, bg_color, fg_color):
        """Recursively theme ALL labels in the history tab"""
        try:
            for child in parent.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        child.configure(bg=bg_color, fg=fg_color)
                    except Exception as e:
                        logger.debug(f"Could not theme label {child}: {e}")
                
                if hasattr(child, 'winfo_children'):
                    self._theme_all_labels_recursive(child, bg_color, fg_color)
                    
        except Exception as e:
            logger.debug(f"Error in recursive label theming: {e}")
    
    def _theme_context_menu(self, bg_color, fg_color, is_dark_mode):
        """Theme the context menu"""
        try:
            if is_dark_mode:
                self.context_menu.configure(
                    bg=bg_color,
                    fg=fg_color,
                    activebackground="#505050",
                    activeforeground=fg_color,
                    relief="flat",
                    bd=0
                )
            else:
                self.context_menu.configure(
                    bg=bg_color,
                    fg=fg_color,
                    activebackground="#e0e0e0",
                    activeforeground=fg_color
                )
        except Exception as e:
            logger.debug(f"Could not theme context menu: {e}")
    
    def _collect_labels(self, parent):
        """Collect all Label widgets for efficient theming"""
        try:
            for child in parent.winfo_children():
                if child.winfo_class() == 'Label':
                    self._label_widgets.append(child)
                if child.winfo_children():
                    self._collect_labels(child)
        except Exception as e:
            logger.debug(f"Could not collect labels from {parent}: {e}")
    
    # ===== DATA MANAGEMENT METHODS =====
    
    def refresh_history(self, event=None):
        """Refresh history display with filters"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        limit = None if self.limit_var.get() == "All" else int(self.limit_var.get())
        history = self.controller.get_tracker_history(limit=limit or 1000)
        
        # Apply filters
        filtered_history = self.apply_filters_to_history(history)
        
        for tracker in filtered_history:
            success_rate = (tracker.success_count / tracker.check_count * 100) if tracker.check_count > 0 else 0
            
            # Color coding based on reliability
            status_icon = "✅" if tracker.alive else "❌"
            if tracker.check_count >= 3:
                if success_rate >= 90:
                    status_icon = "🟢" if tracker.alive else "🔴"
                elif success_rate >= 70:
                    status_icon = "🟡" if tracker.alive else "🟠"
            
            # Determine tracker type from URL
            tracker_type = "Unknown"
            if tracker.url.startswith('udp://'):
                tracker_type = "UDP"
            elif tracker.url.startswith(('http://', 'https://')):
                tracker_type = "HTTP"
            elif tracker.url.startswith('magnet:'):
                tracker_type = "Magnet"
            
            self.tree.insert('', 'end', values=(
                tracker.url,
                f"{status_icon} {'Working' if tracker.alive else 'Dead'}",
                f"{tracker.response_time:.2f}s" if tracker.response_time else "N/A",
                tracker.last_checked[:19] if tracker.last_checked else "Never",
                f"{success_rate:.1f}%",
                tracker.check_count,
                tracker_type
            ))
        
        self.update_stats_dashboard(history)
    
    def apply_filters_to_history(self, history):
        """Apply current filters to history data"""
        filter_type = self.filter_var.get()
        search_term = self.search_var.get().lower()
        
        filtered = history
        
        # Apply type filter
        if filter_type == "Working Only":
            filtered = [t for t in filtered if t.alive]
        elif filter_type == "Dead Only":
            filtered = [t for t in filtered if not t.alive]
        elif filter_type == "High Reliability (>90%)":
            filtered = [t for t in filtered if t.check_count >= 3 and (t.success_count / t.check_count) >= 0.9]
        elif filter_type == "Medium Reliability (70-90%)":
            filtered = [t for t in filtered if t.check_count >= 3 and 0.7 <= (t.success_count / t.check_count) < 0.9]
        elif filter_type == "Low Reliability (<70%)":
            filtered = [t for t in filtered if t.check_count >= 3 and (t.success_count / t.check_count) < 0.7]
        
        # Apply search filter
        if search_term:
            filtered = [t for t in filtered if search_term in t.url.lower()]
        
        return filtered
    
    def update_stats_dashboard(self, history):
        """Update statistics dashboard with current data"""
        if not history:
            return
            
        total = len(history)
        working = sum(1 for t in history if t.alive)
        dead = total - working
        
        # Calculate average success rate
        total_checks = sum(t.check_count for t in history)
        successful_checks = sum(t.success_count for t in history)
        avg_success = (successful_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Reliability breakdown
        high_rel = sum(1 for t in history if t.check_count >= 3 and (t.success_count / t.check_count) >= 0.9)
        medium_rel = sum(1 for t in history if t.check_count >= 3 and 0.7 <= (t.success_count / t.check_count) < 0.9)
        low_rel = sum(1 for t in history if t.check_count >= 3 and (t.success_count / t.check_count) < 0.7)
        
        # Update labels
        self.total_label.config(text=f"Total: {total}")
        self.working_label.config(text=f"Working: {working}")
        self.dead_label.config(text=f"Dead: {dead}")
        self.success_label.config(text=f"Avg Success: {avg_success:.1f}%")
        self.reliability_label.config(text=f"High Rel: {high_rel}")
        self.medium_rel_label.config(text=f"Med Rel: {medium_rel}")
        self.low_rel_label.config(text=f"Low Rel: {low_rel}")
    
    # ===== FILTER AND SEARCH METHODS =====
    
    def apply_filter(self, event=None):
        """Apply selected filter"""
        self.refresh_history()
    
    def apply_search(self, event=None):
        """Apply search filter"""
        self.refresh_history()
    
    def show_reliable(self):
        """Show reliable trackers"""
        self.filter_combo.set("High Reliability (>90%)")
        self.refresh_history()
    
    def show_favorites(self):
        """Show favorite trackers"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        favorites = self.controller.get_favorites()
        for tracker in favorites:
            success_rate = (tracker.success_count / tracker.check_count * 100) if tracker.check_count > 0 else 0
            
            self.tree.insert('', 'end', values=(
                tracker.url,
                "✅ Working" if tracker.alive else "❌ Dead",
                f"{tracker.response_time:.2f}s" if tracker.response_time else "N/A",
                tracker.last_checked[:19] if tracker.last_checked else "Never",
                f"{success_rate:.1f}%",
                tracker.check_count,
                "Favorite"
            ))
    
    # ===== CONTEXT MENU AND INTERACTION METHODS =====
    
    def show_context_menu(self, event):
        """Show right-click context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def add_selected_to_favorites(self):
        """Add selected tracker to favorites"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if values:
                url = values[0]
                self.controller.add_to_favorites(url, "Added from history context menu")
                messagebox.showinfo("Favorite Added", f"Added {url} to favorites!")
    
    def copy_selected_url(self):
        """Copy selected URL to clipboard"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if values:
                url = values[0]
                self.tab.clipboard_clear()
                self.tab.clipboard_append(url)
                messagebox.showinfo("Copied", f"URL copied to clipboard!")
    
    def validate_selected(self):
        """Validate selected tracker again"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if values:
                url = values[0]
                messagebox.showinfo("Re-validate", f"Would re-validate: {url}")
    
    def clear_history(self):
        """Clear all history (with confirmation)"""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all history? This cannot be undone."):
            messagebox.showinfo("Clear History", "History clearance would be implemented here")
            self.refresh_history()
    
    def on_double_click(self, event):
        """Add double-clicked tracker to favorites"""
        selection = self.tree.selection()
        if not selection:
            return
        try:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if values and len(values) > 0:
                url = values[0]
                self.controller.add_to_favorites(url, "Added from history")
                messagebox.showinfo("Favorite Added", f"Added {url} to favorites!")
        except (IndexError, tk.TclError) as e:
            logger.debug(f"Could not add favorite: {e}")