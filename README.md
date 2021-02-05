# PokerNow HUD

Parser and analyzer for logs from [pokernow.club](https://www.pokernow.club)

Check out the Jupyter Notebook for adhoc customizable analysis/dirty data science code.

You will need to download all your own logs from pokernow.club after you've finished a session and dump that log into a single directory. Modify the config.ini file to standardize the logs (which are really really hard to systematically parse)

## Config Schema

#### PATHS
`log_dir` is the directory where your logs are stored

`image_dir` is the base image directory (relative to the repository root)

`pnl_graph_dir` is the image directory to store individual player PnL graphs (relative to the repository root)


#### ALIASES
Sometimes the same players will decide to join sessions with different names. This dictionary will help you aggregate them. If your club has more than one player with the same name and they don't bother to differentiate themselves, you probably need to come up with some more sophisticated logic and find some better friends.

#### REPLACE
This is all of the text in entry that you want to find and replace as a preprocess. Feel free to add some logic to support regex if you want.


## Running the parser

Once you've gathered your logs and set up the `config.ini`, run `python log_parser.py` to generate your output. Any sensible version of Python (>3.6) should work. Here are some of my deps:

```
matplotlib==3.2.2
numpy==1.18.1
pandas==1.1.2
```
