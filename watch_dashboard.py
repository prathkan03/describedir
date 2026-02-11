
import json
import os
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: watchdog not installed.")
    print("Install it with: pip3 install watchdog")
    sys.exit(1)

class DescriptionDashboard:
    """Manages the dashboard display and file tracking."""

    def __init__(self, json_file: str = ".describedir.json"):
        self.json_file = Path(json_file)
        self.data = None
        self.changed_files: Set[str] = set()
        self.last_update = None
        self.load_data()

    def load_data(self) -> None:
        """Load the JSON description file."""
        if not self.json_file.exists():
            print(f"Error: {self.json_file} not found.")
            print("Run 'python3 -m describedir' first.")
            sys.exit(1)

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
                self.last_update = datetime.now()
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}")
            sys.exit(1)

    def add_changed_file(self, filepath: str) -> None:
        """Track a changed file."""
        try:
            rel_path = Path(filepath).relative_to(Path.cwd())
            self.changed_files.add(str(rel_path))
        except ValueError:
            # If relative_to fails, just use the path as-is
            self.changed_files.add(filepath)

    def clear_changed_files(self) -> None:
        """Clear the changed files list."""
        self.changed_files.clear()

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system("clear" if os.name != "nt" else "cls")

    def print_dashboard(self) -> None:
        """Print the live dashboard."""
        self.clear_screen()

        # Header
        print("\n" + "=" * 100)
        print(f"📊 DESCRIBEDIR LIVE DASHBOARD")
        print("=" * 100)

        # Project info
        print(f"\n📦 Project: {self.data['tree']['name']}")
        print(f"📍 Root: {self.data['root']}")
        print(f"🤖 Model: {self.data['model']}")
        print(f"⏰ Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")

        # Project description
        print(f"\n📝 Description:")
        print(f"   {self.data['tree']['description']}")

        # Changed files section
        if self.changed_files:
            print(f"\n🔴 CHANGED FILES ({len(self.changed_files)}):") 
            print("-" * 100)
            for filepath in sorted(self.changed_files):
                print(f"   • {filepath}")
        else:
            print(f"\n✅ No changes detected")

        # Directory structure summary
        print(f"\n📂 DIRECTORY STRUCTURE:")
        print("-" * 100)
        self._print_tree_summary(self.data["tree"], depth=0)

        # Footer
        print("\n" + "=" * 100)
        print("Watching for changes... Press Ctrl+C to stop")
        print("=" * 100 + "\n")

    def _print_tree_summary(self, node: dict, depth: int = 0) -> None:
        """Print a summary of the directory tree."""
        if depth > 3:  # Limit depth for readability
            return

        indent = "   " * depth
        icon = "📁" if node["type"] == "directory" else "📄"
        name = node["name"]

        # Highlight changed files
        is_changed = node["path"] in self.changed_files
        marker = " 🔴" if is_changed else ""

        print(f"{indent}{icon} {name}{marker}")

        if node.get("description"):
            desc = node["description"]
            if len(desc) > 70:
                desc = desc[:67] + "..."
            print(f"{indent}   └─ {desc}")

        # Print children
        children = node.get("children", [])
        for child in children:
            self._print_tree_summary(child, depth + 1)


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events."""

    def __init__(self, dashboard: DescriptionDashboard, ignore_patterns: list, refresh_interval: float = 1.0):
        self.dashboard = dashboard
        self.ignore_patterns = ignore_patterns
        self.debounce_timer = None
        self.debounce_delay = 2  # seconds
        self.refresh_interval = refresh_interval
        self.refresh_thread = None
        self.running = False

    def should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        for pattern in self.ignore_patterns:
            if pattern in path:
                return True
        return False

    def on_modified(self, event) -> None:
        """Handle file modification."""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        self.dashboard.add_changed_file(event.src_path)
        self.schedule_update()

    def on_created(self, event) -> None:
        """Handle file creation."""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        self.dashboard.add_changed_file(event.src_path)
        self.schedule_update()

    def on_deleted(self, event) -> None:
        """Handle file deletion."""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        self.dashboard.add_changed_file(event.src_path)
        self.schedule_update()

    def schedule_update(self) -> None:
        """Schedule a debounced update."""
        # Cancel previous timer if exists
        if self.debounce_timer:
            self.debounce_timer.cancel()

        # Schedule new update
        self.debounce_timer = threading.Timer(
            self.debounce_delay, self.run_describedir
        )
        self.debounce_timer.daemon = True
        self.debounce_timer.start()

    def run_describedir(self) -> None:
        """Run describedir to update descriptions."""
        print("\n🔄 Updating descriptions...")
        try:
            # Run describedir using subprocess with the same Python interpreter
            result = subprocess.run(
                [sys.executable, "-m", "describedir"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.dashboard.load_data()
                self.dashboard.clear_changed_files()
                self.dashboard.print_dashboard()
            else:
                print(f"Error running describedir: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("Error: describedir took too long to run")
        except Exception as e:
            print(f"Error: {e}")

    def start_refresh_loop(self) -> None:
        """Start the periodic refresh loop."""
        self.running = True
        self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.refresh_thread.start()

    def stop_refresh_loop(self) -> None:
        """Stop the periodic refresh loop."""
        self.running = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=2)

    def _refresh_loop(self) -> None:
        """Periodically refresh the dashboard display."""
        while self.running:
            time.sleep(self.refresh_interval)
            if self.dashboard.changed_files:
                self.dashboard.print_dashboard()


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Watch for file changes and display live dashboard of descriptions"
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to watch (default: current directory)",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".describedir.json"],
        help="Patterns to ignore",
    )

    args = parser.parse_args()

    # Initialize dashboard
    dashboard = DescriptionDashboard()
    dashboard.print_dashboard()

    # Set up file watcher
    event_handler = FileChangeHandler(dashboard, args.ignore)
    observer = Observer()
    observer.schedule(event_handler, args.path, recursive=True)

    try:
        observer.start()
        event_handler.start_refresh_loop()
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Stopping dashboard...")
        event_handler.stop_refresh_loop()
        observer.stop()
    finally:
        observer.join()


if __name__ == "__main__":
    main()