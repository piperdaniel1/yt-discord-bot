from yt_dl import *
import os

media_dir = os.listdir(MEDIA_PATH)

for media in media_dir:
    full_path = f"{MEDIA_PATH}/{media}"
    if not os.path.isfile(full_path) or media == ".mediacache":
        continue

    new_title = simplify_song_title(media)
    new_path = f"{MEDIA_PATH}/{new_title}"

    if new_path != full_path:
        print(f"Renaming {media} to {new_title}")
        os.rename(full_path, new_path)
