# ProfileBot

ProfileBot is a bot designed to keep track of, basically, form data from a user. The idea came from making a system for a furry server to fill out their sonas into the bot, and I figured I could make this into a more generalised system for people to use.

# Goals

The goals of this project are ultimately pretty simple, but may take a while to implement in the way I want it to work1.

* Allow moderators to set profiles for users to fill
    * Profiles can have an unlimited (unless restricted by Discord) amount of fields
    * Restrictions on field data must be set by the moderators of the profile
    * Profile moderators can verifiy/deny/delete sonas as they see fit
* Allow a user to fill out a profile as created by a moderator
* Allow users to pull up another user's profile
* Allow multiple profiles per guild

# Technologies

I'm going to be using Discord.py, because I like Python, and asyncpg, since the Postgres database driver is the fastest that async Python has. A mistake I learned late into another project of mine, [MarriageBot](https://github.com/4Kaylum/MarriageBot) is that if you want to make it modular enough to run multiple instances, you should probably do it early. It's for that reason that I'm also going to be using aioredis and a Redis server.

Apart from those three, I'm not sure what else I could need, but I'm sure I'll end up needing more by the end of the project. See my [requirements](requirements.txt) file.
