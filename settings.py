import json, sys, os

def stripper(f):
    """
    In my mind this function was way cooler, and deserved the name it has.

    This takes a file and strips out any comments. It's a cheaty way of
    adding comments to json files. Cuz I like comments. And I like json.
    """
    new = []  # If this was php we'd be fucked
    for line in f.readlines():
        if line.strip().startswith("//"):
            continue
        if '//' in line.strip():
            new.append(line.strip().split("//", 1)[0])
            continue
        new.append(line.rstrip())
    return "\n".join(new)

DEFAULT_CONFIG = """
{
    // Obtain this from http://www.themoviedb.org/documentation/api
    "TMDB_API_KEY": "",

    // Transmission Information
    "transmission": {
        // Hostname or IP (usually localhost)
        "host": "localhost",
        // Port (default 9091)
        "port": 9091
    },

    "torrents": {
        // A list of file formats that are preferable (helps in choosing torrents)
        "best_formats": ["mkv"]
    },

    "storage": {
        // Modes:
        //   None: Simply leaves the files in the default download directory (does not rename/etc)
        //   Recursive: Creates a recursive directory structure at `dir` 
        //   Single: Stores files in a single folder at `dir`
        //   Archival: Stores files for `days` in folder `dir`
        "type": "none",
        "dir": "~/Videos",
        // The default format for recursive directory structures
        "dir_format": "{show}/{season}/{episode}",
        "days": 7,
        // The file name format. Keys:
        //  episode, season, show
        // name_ds (dot seperated), name_us (underscore seperated), name
        "file_format": "S{season}E{episode}-{name_ds}"
    }
}
"""

def load_config():
    if not os.path.exists("config.json"):
        print "Could not find config file, dumping default..."
        with open("config.json", "w") as f:
            f.write(DEFAULT_CONFIG)
        print "Dumped config! Please edit and try again!"
        sys.exit()

    with open("config.json", "r") as f:
        return json.loads(stripper(f))

config = load_config()