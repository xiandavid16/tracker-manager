import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import logging
from typing import List
from models.database_models import TrackerHistory
import sys

logger = logging.getLogger(__name__)

class DarkTreeview(ttk.Treeview):
    """A Treeview that properly supports dark mode headers"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_dark = False
        self._style = ttk.Style()
        
    def set_dark_mode(self, is_dark):
        """Enable or disable dark mode"""
        self._is_dark = is_dark
        self._update_style()
        
    def _update_style(self):
        """Update the style for dark mode"""
        try:
            if self._is_dark:
                # Configure Treeview for dark mode
                self._style.configure("Treeview",
                    background="#2a2a2a",
                    foreground="#e8e8e8",
                    fieldbackground="#2a2a2a",
                    borderwidth=0
                )
                
                # Configure Treeview Heading for dark mode
                self._style.configure("Treeview.Heading",
                    background="#404040",
                    foreground="#e8e8e8",
                    relief="flat",
                    borderwidth=1
                )
                
                # Override active state to prevent white hover
                self._style.map("Treeview.Heading",
                    background=[('active', '#505050')],
                    foreground=[('active', '#e8e8e8')]
                )
                
                # Configure selected items
                self._style.map("Treeview",
                    background=[('selected', '#505050')],
                    foreground=[('selected', '#e8e8e8')]
                )
                
            else:
                # Reset to default styles for light mode
                self._style.configure("Treeview",
                    background="white",
                    foreground="black",
                    fieldbackground="white"
                )
                
                self._style.configure("Treeview.Heading",
                    background="#f5f5f5",
                    foreground="#333333",
                    relief="raised"
                )
                
                self._style.map("Treeview.Heading",
                    background=[('active', '#e0e0e0')],
                    foreground=[('active', '#333333')]
                )
                
                self._style.map("Treeview",
                    background=[('selected', '#e0e0e0')],
                    foreground=[('selected', 'black')]
                )
                
            # Force update
            self.update_idletasks()
            
        except Exception as e:
            logger.debug(f"Treeview theme error: {e}")
            
class HistoryView:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.sort_column = None        
        self.sort_reverse = False
        self.current_history_data = []

        self.setup_gui()
               
        # Apply theme after UI is fully loaded
        self.tab.after(500, self.delayed_theme_refresh)
        
        self.refresh_history()

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
        
        ttk.Button(top_controls, text="📤 Export (Exclude 0%)", 
                 command=self.export_excluding_zero_success).pack(side='left', padx=(10, 0))

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
        
        # Search box - USED REGULAR TK ENTRY INSTEAD OF TTK FOR BETTER THEMING
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
        self.tree = DarkTreeview(self.tab, columns=columns, show='headings', height=15) 

        # Configure columns
        self.tree.heading('URL', text='URL', command=lambda: self.sort_by_column('URL'))
        self.tree.heading('Status', text='Status', command=lambda: self.sort_by_column('Status'))
        self.tree.heading('Response Time', text='Response Time', command=lambda: self.sort_by_column('Response Time'))
        self.tree.heading('Last Checked', text='Last Checked', command=lambda: self.sort_by_column('Last Checked'))
        self.tree.heading('Success Rate', text='Success Rate', command=lambda: self.sort_by_column('Success Rate'))
        self.tree.heading('Checks', text='Checks', command=lambda: self.sort_by_column('Checks'))
        self.tree.heading('Type', text='Type', command=lambda: self.sort_by_column('Type'))
        
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
        """Setup icon-based mini dashboard that follows clam theme"""
        stats_frame = ttk.LabelFrame(self.tab, text="Quick Stats", padding=8)
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x')
        
        # Compact grid with icons
        stats_data = [
            ('📊', 'total', 'Total: 0'),
            ('✅', 'working', 'Working: 0'), 
            ('🟢', 'high', 'High: 0'),
            ('🟡', 'medium', 'Med: 0'),
            ('🔴', 'low', 'Low: 0'),
            ('❌', 'dead', 'Dead: 0'),
            ('📈', 'success', 'Success: 0%')
        ]
        
        self.stat_labels = {}
        for i, (icon, key, text) in enumerate(stats_data):
            # Use ttk.Frame for consistent theming
            frame = ttk.Frame(stats_grid)
            frame.grid(row=0, column=i, padx=8, pady=2)
            
            # Use ttk.Label for icons to match theme
            icon_label = ttk.Label(frame, text=icon, font=("Arial", 10))
            icon_label.pack(side='left')
            
            # Use ttk.Label for stats to match theme
            stat_label = ttk.Label(frame, text=text, font=("Arial", 9))
            stat_label.pack(side='left', padx=(2, 0))
            
            self.stat_labels[key] = stat_label
        
        # Store references to the main stat labels for theming
        self.total_label = self.stat_labels['total']
        self.working_label = self.stat_labels['working']
        self.dead_label = self.stat_labels['dead']
        self.success_label = self.stat_labels['success']
        self.reliability_label = self.stat_labels['high']
        self.medium_rel_label = self.stat_labels['medium']
        self.low_rel_label = self.stat_labels['low']
    
    # ===== THEMING METHODS =====

    def delayed_theme_refresh(self):
        """Refresh theme after UI is fully loaded"""
        try:
            print("Delayed theme refresh for history view", file=sys.stderr)
            # Re-apply theme after a short delay
            self.tab.after(1000, lambda: self.apply_theme("#2a2a2a", "#e8e8e8", "#2a2a2a", "#e8e8e8"))
        except Exception as e:
            print(f"Delayed theme error: {e}", file=sys.stderr)

    #def _bind_header_debug(self):
        """Bind debug events to headers"""
        try:
            def on_enter(event):
                widget = event.widget
                print(f"Mouse ENTERED: {widget} - Class: {widget.winfo_class()}", file=sys.stderr)
                try:
                    print(f"  BG: {widget.cget('background')}, FG: {widget.cget('foreground')}", file=sys.stderr)
                except:
                    print("  Could not get colors", file=sys.stderr)
                
            def on_leave(event):
                print(f"Mouse LEFT: {event.widget}", file=sys.stderr)
                
            # Bind to the treeview and all its children
            self.tree.bind('<Enter>', on_enter)
            self.tree.bind('<Leave>', on_leave)
            
            # Also try to bind to any existing headers
            def bind_headers():
                for child in self.tree.winfo_children():
                    for grandchild in child.winfo_children():
                        if grandchild.winfo_class() in ['TButton', 'Button']:
                            grandchild.bind('<Enter>', on_enter)
                            grandchild.bind('<Leave>', on_leave)
                            print(f"Bound to header: {grandchild}", file=sys.stderr)
            
            # Bind after a short delay to ensure headers exist
            self.tree.after(1000, bind_headers)
            
        except Exception as e:
            print(f"Header debug bind failed: {e}", file=sys.stderr) 

    def apply_theme(self, bg_color, fg_color, text_bg, text_fg):
        """Apply theme to history tab widgets - SIMPLIFIED AND FOCUSED"""
        try:
            # Get dark mode state safely
            is_dark_mode = False
            try:
                # Try multiple ways to get dark mode state
                if hasattr(self.controller, 'main_view') and hasattr(self.controller.main_view, 'is_dark_mode'):
                    is_dark_mode = self.controller.main_view.is_dark_mode
                elif hasattr(self.controller, 'is_dark_mode'):
                    is_dark_mode = self.controller.is_dark_mode
                else:
                    # Fallback: check if we're using dark colors
                    is_dark_mode = bg_color != "#f0f0f0"  # Light mode default
            except:
                is_dark_mode = False
            
            print(f"=== APPLYING HISTORY THEME (dark: {is_dark_mode}) ===", file=sys.stderr)
            
            if is_dark_mode:
                # DARK MODE
                self._apply_dark_theme(bg_color, fg_color)
                
                # Use our custom treeview's dark mode
                if hasattr(self.tree, 'set_dark_mode'):
                    self.tree.set_dark_mode(True)
                    print("Applied dark mode to custom treeview", file=sys.stderr)
                    
            else:
                # LIGHT MODE
                self._apply_light_theme(bg_color, fg_color, text_bg)
                
                # Use light mode
                if hasattr(self.tree, 'set_dark_mode'):
                    self.tree.set_dark_mode(False)
                    print("Applied light mode to custom treeview", file=sys.stderr)
                
            # Theme all labels
            self._theme_all_labels(bg_color, fg_color, is_dark_mode)
            
            # Theme context menu
            self._theme_context_menu(bg_color, fg_color, is_dark_mode)
            
            print("=== HISTORY THEME APPLIED ===", file=sys.stderr)
            
        except Exception as e:
            logger.debug(f"Could not theme history view: {e}")
            print(f"History theme error: {e}", file=sys.stderr)

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
    
    #def _theme_all_labels(self, bg_color, fg_color, is_dark_mode):
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
    
    #def _theme_all_labels_recursive(self, parent, bg_color, fg_color):
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
    #===
    #===
    # ===== DATA MANAGEMENT METHODS =====

    def export_excluding_zero_success(self):
        """Export all trackers except those with 0% success rate"""
        try:
            trackers = self.get_trackers_excluding_zero_success()
            
            if not trackers:
                messagebox.showinfo("No Data", "No trackers to export (all have 0% success rate)")
                return
            
            # Create export content
            content = "\n".join([tracker.url for tracker in trackers])
            
            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Trackers (Excluding 0% Success)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                zero_count = len([t for t in self.controller.get_tracker_history() if t.check_count > 0 and (t.success_count / t.check_count) == 0])
                messagebox.showinfo("Export Complete", 
                                f"Exported {len(trackers)} trackers (excluding {zero_count} with 0% success rate)\n\nFile: {file_path}")
                self.controller.main_view.update_status(f"Exported {len(trackers)} trackers excluding {zero_count} with 0% success")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export: {e}")

    def get_trackers_excluding_zero_success(self):
        """Get all trackers except those with 0% success rate"""
        history = self.controller.get_tracker_history(limit=1000)  # Get all history
        return [tracker for tracker in history if tracker.check_count == 0 or (tracker.success_count / tracker.check_count) > 0]

    def refresh_history(self, event=None):
        """Refresh history display with filters and sorting"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        limit = None if self.limit_var.get() == "All" else int(self.limit_var.get())
        history = self.controller.get_tracker_history(limit=limit or 1000)
        
        # Apply filters and store the result
        filtered_history = self.apply_filters_to_history(history)
        self.current_history_data = filtered_history  # Store for sorting
        
        # Display with current sorting (or default if no sorting set)
        self.display_sorted_data()
        
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

    def sort_by_column(self, column):
        """Sort treeview by clicked column with visual indicators and proper theming"""
        # Toggle sort direction if same column clicked again
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        # Update column headers with sort indicators
        for col in ['URL', 'Status', 'Response Time', 'Last Checked', 'Success Rate', 'Checks', 'Type']:
            current_text = self.tree.heading(col, 'text')
            # Remove existing sort indicators
            clean_text = current_text.replace(' ▲', '').replace(' ▼', '')
            if col == column:
                # Add new sort indicator
                indicator = ' ▼' if self.sort_reverse else ' ▲'
                self.tree.heading(col, text=clean_text + indicator)
            else:
                self.tree.heading(col, text=clean_text)
        
        # Re-display data with new sort order
        self.display_sorted_data()

    def display_sorted_data(self):
        """Display data sorted by current sort column and direction"""
        if not self.current_history_data:
            return
        
        # Clear current display
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Sort the data
        sorted_data = self.apply_sorting(self.current_history_data)
        
        # Re-insert sorted data
        for tracker in sorted_data:
            success_rate = (tracker.success_count / tracker.check_count * 100) if tracker.check_count > 0 else 0
            
            status_icon = "✅" if tracker.alive else "❌"
            if tracker.check_count >= 3:
                if success_rate >= 90:
                    status_icon = "🟢" if tracker.alive else "🔴"
                elif success_rate >= 70:
                    status_icon = "🟡" if tracker.alive else "🟠"
            
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

    def apply_sorting(self, data):
            """Apply sorting to data based on current sort column"""
            if not self.sort_column:
                return data
            
            def sort_key(tracker):
                if self.sort_column == 'URL':
                    return tracker.url.lower()
                elif self.sort_column == 'Status':
                    return tracker.alive
                elif self.sort_column == 'Response Time':
                    return tracker.response_time or 0
                elif self.sort_column == 'Last Checked':
                    return tracker.last_checked or ''
                elif self.sort_column == 'Success Rate':
                    return (tracker.success_count / tracker.check_count) if tracker.check_count > 0 else 0
                elif self.sort_column == 'Checks':
                    return tracker.check_count
                elif self.sort_column == 'Type':
                    if tracker.url.startswith('udp://'):
                        return 'UDP'
                    elif tracker.url.startswith(('http://', 'https://')):
                        return 'HTTP'
                    elif tracker.url.startswith('magnet:'):
                        return 'Magnet'
                    return 'Unknown'
                return ''
            
            return sorted(data, key=sort_key, reverse=self.sort_reverse)

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
    
    #def refresh_treeview_headers(self):
        """Force refresh treeview headers to apply theme"""
        try:

            
            # Update all column headings to trigger redraw
            for col in ['URL', 'Status', 'Response Time', 'Last Checked', 'Success Rate', 'Checks', 'Type']:
                current_text = self.tree.heading(col, 'text')
                self.tree.heading(col, text=current_text)  # Reset to force redraw
            
            self.tree.update_idletasks()
        except Exception as e:
            logger.debug(f"Could not refresh treeview headers: {e}")

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
        """Clear all history (with confirmation and proper implementation)"""
        # Get current stats for confirmation message
        try:
            stats = self.controller.database.get_history_stats()
            
            if stats['trackers'] == 0 and stats['sessions'] == 0:
                messagebox.showinfo("Clear History", "History is already empty!")
                return
            
            # Create detailed confirmation message
            confirmation_msg = [
                "Are you sure you want to clear ALL history?",
                "This cannot be undone!",
                "",
                f"• Trackers: {stats['trackers']} records",
                f"• Validation Sessions: {stats['sessions']} records",
                f"• Favorites: {stats['favorites']} records",
                "",
                "This will remove all tracker validation history and statistics."
            ]
            
            if messagebox.askyesno("Clear History - CONFIRM", "\n".join(confirmation_msg)):
                # Ask if they want to preserve favorites
                preserve_favorites = True
                if stats['favorites'] > 0:
                    preserve_favorites = messagebox.askyesno(
                        "Preserve Favorites?", 
                        f"Do you want to preserve your {stats['favorites']} favorite trackers?"
                    )
                
                # Perform the clearing
                if preserve_favorites:
                    self.controller.database.clear_tracker_history()
                    action = "History cleared (favorites preserved)"
                else:
                    self.controller.database.clear_all_history()
                    action = "All history cleared including favorites"
                
                # Refresh the display
                self.refresh_history()
                
                # Show completion message
                messagebox.showinfo("Clear History", f"{action}!\n\nAll history has been cleared successfully.")
                
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
            messagebox.showerror("Error", f"Could not clear history: {e}")
    
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