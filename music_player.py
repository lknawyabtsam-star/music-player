"""Music Player - a Tkinter + pygame MP3 player built on a doubly linked list."""

import os
import random
import time
import tkinter as tk
from tkinter import messagebox

import pygame

try:  # Optional: gives fast, cheap song-length lookups.
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

BG = "#ffe6f0"
PINK_DARK = "#ff3399"
PINK_MAIN = "#ff99cc"
PINK_LIGHT = "#ffb6c1"
FONT = "Comic Sans MS"
LIST_FONT = ("Segoe UI", 11, "bold")


# ---------------- DATA STRUCTURES ---------------- #
class Node:
    def __init__(self, title, file_path):
        self.title = title
        self.file_path = file_path
        self.next = None  # Points to next node
        self.prev = None  # Points to previous node - this makes it DOUBLY linked


class Playlist:
    """Doubly linked list of songs with a 'current' pointer."""

    def __init__(self):
        self.head = None     # First node
        self.tail = None     # Last node
        self.current = None  # Currently selected node
        self.size = 0

    def add_song(self, title, file_path):
        new_node = Node(title, file_path)
        if not self.head:
            self.head = new_node
            self.tail = new_node
            self.current = new_node
        else:
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        self.size += 1

    def remove_song(self, node):
        if not node:
            return False

        if node.prev:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        if self.current is node:
            # Move on to the neighbour instead of jumping back to the start.
            self.current = node.next or node.prev

        self.size -= 1
        return True

    def get_node_at(self, index):
        curr = self.head
        for _ in range(index):
            if not curr:
                break
            curr = curr.next
        return curr

    def index_of(self, node):
        index = 0
        curr = self.head
        while curr and curr is not node:
            curr = curr.next
            index += 1
        return index

    def next_current(self):
        if self.current and self.current.next:
            self.current = self.current.next
        elif self.current:
            self.current = self.head  # wrap around

    def prev_current(self):
        if self.current and self.current.prev:
            self.current = self.current.prev
        elif self.current:
            self.current = self.tail  # wrap around


# ---------------- MUSIC PLAYER ---------------- #
class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("700x700")
        self.root.configure(bg=BG)

        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.music.set_volume(0.7)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.music_folder = os.path.join(self.base_dir, "music")

        self.playlist = Playlist()
        self.history = []
        self.shuffle = False
        self.repeat = False
        self.is_paused = False
        self.current_time = 0
        self.song_duration = 0
        self.start_time = 0

        self.MUSIC_END = pygame.USEREVENT + 1
        pygame.mixer.music.set_endevent(self.MUSIC_END)

        self.load_songs()
        self.create_ui()

        self.check_events()
        self.update_time_display()

    # ---------------- LOAD SONGS ---------------- #
    def load_songs(self):
        os.makedirs(self.music_folder, exist_ok=True)

        for file in sorted(os.listdir(self.music_folder)):
            if file.lower().endswith(".mp3"):
                title = os.path.splitext(file)[0]
                path = os.path.join(self.music_folder, file)
                self.playlist.add_song(title, path)

        if self.playlist.size == 0:
            messagebox.showwarning(
                "No songs found",
                f"Add some .mp3 files to this folder and restart:\n{self.music_folder}",
            )

    # ---------------- UI ---------------- #
    def _button(self, parent, text, command, bg, row, col):
        btn = tk.Button(
            parent,
            text=text,
            width=12,
            bg=bg,
            fg="white",
            font=(FONT, 10, "bold"),
            command=command,
        )
        btn.grid(row=row, column=col, padx=6, pady=6)
        return btn

    def create_ui(self):
        top_frame = tk.Frame(self.root, bg=BG)
        top_frame.pack(pady=10)

        tk.Label(
            top_frame,
            text="🎀 Music Player 🎀",
            font=(FONT, 24, "bold"),
            bg=BG,
            fg="#ff4da6",
        ).pack()

        self.current_frame = tk.Frame(
            self.root, bg="#ffccf2", relief="raised", bd=3, height=60
        )
        self.current_frame.pack(pady=10, padx=50, fill="x")
        self.current_frame.pack_propagate(False)

        self.current_label = tk.Label(
            self.current_frame,
            text="No song selected",
            font=(FONT, 16, "bold"),
            fg=PINK_DARK,
            bg="#ffccf2",
        )
        self.current_label.pack(expand=True)

        self.progress_label = tk.Label(
            self.root,
            text="00:00 / 00:00",
            fg="#ff66cc",
            bg=BG,
            font=(FONT, 12),
        )
        self.progress_label.pack(pady=5)

        lists_frame = tk.Frame(self.root, bg=BG)
        lists_frame.pack(pady=10, fill="both", expand=True)

        # Playlist column
        playlist_frame = tk.Frame(lists_frame, bg=BG)
        playlist_frame.pack(side="left", padx=20, fill="both", expand=True)

        tk.Label(
            playlist_frame,
            text="🎵 Playlist",
            fg=PINK_DARK,
            bg=BG,
            font=(FONT, 14, "bold"),
        ).pack()

        self.listbox = tk.Listbox(
            playlist_frame,
            bg="#fff0f5",
            fg=PINK_DARK,
            selectbackground=PINK_LIGHT,
            height=15,
            font=LIST_FONT,
            exportselection=False,  # keep selection when clicking elsewhere
        )
        self.listbox.pack(pady=5, fill="both", expand=True)
        self.listbox.bind("<ButtonRelease-1>", self.on_playlist_click)
        self.refresh_playlist_box()

        # History column
        history_frame = tk.Frame(lists_frame, bg=BG)
        history_frame.pack(side="right", padx=20, fill="both", expand=True)

        tk.Label(
            history_frame,
            text="📜 Playback History",
            fg=PINK_DARK,
            bg=BG,
            font=(FONT, 14, "bold"),
        ).pack()

        self.history_listbox = tk.Listbox(
            history_frame,
            bg="#fff0f5",
            fg=PINK_DARK,
            height=15,
            font=LIST_FONT,
            exportselection=False,
        )
        self.history_listbox.pack(pady=5, fill="both", expand=True)

        # Controls
        controls = tk.Frame(self.root, bg=BG)
        controls.pack(pady=20)

        self._button(controls, "▶️ Play", self.play, PINK_MAIN, 0, 0)
        self._button(controls, "⏸️ Pause", self.pause, PINK_MAIN, 0, 1)
        self._button(controls, "⏭️ Next", self.next_song, PINK_MAIN, 0, 2)
        self._button(controls, "⏮️ Prev", self.prev_song, PINK_MAIN, 0, 3)
        self.shuffle_btn = self._button(
            controls, "🔀 Shuffle", self.toggle_shuffle, PINK_MAIN, 0, 4
        )

        self.repeat_btn = self._button(
            controls, "🔁 Repeat", self.toggle_repeat, PINK_LIGHT, 1, 0
        )
        self._button(controls, "🔊 Volume +", self.volume_up, PINK_LIGHT, 1, 1)
        self._button(controls, "🔉 Volume -", self.volume_down, PINK_LIGHT, 1, 2)
        self._button(controls, "📜 History", self.show_history_popup, PINK_LIGHT, 1, 3)
        self._button(controls, "🗑️ Remove", self.remove_song, PINK_LIGHT, 1, 4)

        self.volume_label = tk.Label(
            self.root,
            text=f"Volume: {int(pygame.mixer.music.get_volume() * 100)}%",
            fg="#ff66cc",
            bg=BG,
            font=(FONT, 12),
        )
        self.volume_label.pack(pady=5)

    def refresh_playlist_box(self):
        self.listbox.delete(0, tk.END)
        index = 1
        curr = self.playlist.head
        while curr:
            self.listbox.insert(tk.END, f"{index}. {curr.title}")
            curr = curr.next
            index += 1

    def refresh_history_box(self):
        self.history_listbox.delete(0, tk.END)
        for node in self.history:
            self.history_listbox.insert(tk.END, node.title)

    # ---------------- EVENTS AND TIMERS ---------------- #
    def check_events(self):
        for event in pygame.event.get():
            if event.type == self.MUSIC_END:
                self.on_song_end()
        self.root.after(100, self.check_events)

    def on_song_end(self):
        # Ignore stale events: a new track is already playing, or we're paused.
        if pygame.mixer.music.get_busy() or self.is_paused:
            return
        if not self.playlist.current:
            return
        if self.repeat:
            self.restart_current_song()
        else:
            self.next_song()

    def restart_current_song(self):
        if self.playlist.current:
            pygame.mixer.music.load(self.playlist.current.file_path)
            pygame.mixer.music.play()
            self.start_time = time.time()
            self.current_time = 0

    def update_time_display(self):
        if pygame.mixer.music.get_busy() and not self.is_paused:
            elapsed = int(time.time() - self.start_time)
            if self.song_duration > 0:
                elapsed = min(elapsed, self.song_duration)
            self.current_time = elapsed
            self.progress_label.config(
                text=f"{self.format_time(elapsed)} / {self.format_time(self.song_duration)}"
            )
        # Always reschedule so the display keeps updating for later songs.
        self.root.after(500, self.update_time_display)

    @staticmethod
    def format_time(seconds):
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"

    def get_song_length(self, path):
        if MP3 is not None:
            try:
                return int(MP3(path).info.length)
            except Exception:
                pass
        return int(pygame.mixer.Sound(path).get_length())

    # ---------------- PLAYLIST INTERACTIONS ---------------- #
    def on_playlist_click(self, event):
        selection = self.listbox.curselection()
        if selection:
            node = self.playlist.get_node_at(selection[0])
            if node:
                self.playlist.current = node
                self.play_current()

    # ---------------- PLAYER CONTROLS ---------------- #
    def play(self):
        if self.is_paused:  # resume instead of restarting
            self.pause()
            return
        if not self.playlist.current and self.playlist.head:
            self.playlist.current = self.playlist.head
        self.play_current()

    def play_current(self):
        node = self.playlist.current
        if not node:
            return
        try:
            pygame.mixer.music.load(node.file_path)
            pygame.mixer.music.play()
            self.current_label.config(text=node.title)

            index = self.playlist.index_of(node)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)

            if not self.history or self.history[-1] is not node:
                self.history.append(node)
                self.history_listbox.insert(tk.END, node.title)

            self.is_paused = False
            self.start_time = time.time()
            self.current_time = 0
            self.song_duration = self.get_song_length(node.file_path)
            self.progress_label.config(
                text=f"00:00 / {self.format_time(self.song_duration)}"
            )
        except pygame.error as e:
            messagebox.showerror("Error", f"Cannot play: {e}")

    def pause(self):
        if pygame.mixer.music.get_busy() or self.is_paused:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.start_time = time.time() - self.current_time
            else:
                pygame.mixer.music.pause()
                self.current_time = int(time.time() - self.start_time)
            self.is_paused = not self.is_paused

    def next_song(self):
        if not self.playlist.current:
            return
        if self.shuffle and self.playlist.size > 1:
            current_index = self.playlist.index_of(self.playlist.current)
            indices = [i for i in range(self.playlist.size) if i != current_index]
            self.playlist.current = self.playlist.get_node_at(random.choice(indices))
        else:
            self.playlist.next_current()
        self.play_current()

    def prev_song(self):
        if not self.playlist.current:
            return
        if len(self.history) > 1:
            self.history.pop()
            self.playlist.current = self.history[-1]
            self.refresh_history_box()
        else:
            self.playlist.prev_current()
        self.play_current()

    # ---------------- TOGGLES & VOLUME ---------------- #
    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.shuffle_btn.config(relief="sunken" if self.shuffle else "raised")

    def toggle_repeat(self):
        self.repeat = not self.repeat
        self.repeat_btn.config(relief="sunken" if self.repeat else "raised")

    def volume_up(self):
        v = min(1.0, pygame.mixer.music.get_volume() + 0.1)
        pygame.mixer.music.set_volume(v)
        self.volume_label.config(text=f"Volume: {int(v * 100)}%")

    def volume_down(self):
        v = max(0.0, pygame.mixer.music.get_volume() - 0.1)
        pygame.mixer.music.set_volume(v)
        self.volume_label.config(text=f"Volume: {int(v * 100)}%")

    # ---------------- HISTORY & REMOVE ---------------- #
    def show_history_popup(self):
        messagebox.showinfo(
            "Playback History",
            "\n".join(n.title for n in self.history) or "Empty",
        )

    def remove_song(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Remove", "Select a song")
            return

        node = self.playlist.get_node_at(selection[0])
        if node is None:
            return
        if not messagebox.askyesno("Remove", f"Remove '{node.title}'?"):
            return

        was_current = node is self.playlist.current
        was_playing = pygame.mixer.music.get_busy() or self.is_paused

        self.playlist.remove_song(node)
        self.history = [h for h in self.history if h is not node]
        self.refresh_playlist_box()
        self.refresh_history_box()

        if was_current:
            pygame.mixer.music.stop()
            self.is_paused = False
            if self.playlist.current and was_playing:
                self.play_current()  # carry on with the neighbouring song
            else:
                self.current_label.config(text="No song selected")
                self.progress_label.config(text="00:00 / 00:00")

    # ---------------- SHUTDOWN ---------------- #
    def on_close(self):
        self.root.destroy()
        pygame.quit()


# ---------------- RUN APP ---------------- #
if __name__ == "__main__":
    root = tk.Tk()
    player = MusicPlayer(root)
    root.protocol("WM_DELETE_WINDOW", player.on_close)
    root.mainloop()
