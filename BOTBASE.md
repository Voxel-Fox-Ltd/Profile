# ProfileBot

A bot designed to track form data from users. It's a powerful system set up entirely by the server itself so mods can decide exactly what they want added to their server.

## What does it do?

ProfileBot allows you to create forms for users to fill in, which you can then view at any point on the server. This can be useful for storing things like character data for RP servers, or in-game data for gamers, or things along those lines.

Here you can see an example of a created profile:

![An image of a Discord embed showing information about Harry Potter](/marketing/filled_profile.png)

And with that fairly boring example out of the way, here's an example of how to set up and fill in a profile, so you can see just how powerful this system can be.

![A gif of a profile template being setup](/marketing/create_template.gif)
![A gif of a profile template being filled in](/marketing/set_profile.gif)

## How do I do it?

The most simple way to check what you can do is to run `,help`, which will PM you all of the bot's commands.

ALTERNATIVELY: I'll list them all here for you <3

* `,help` - Show all of the commands the bot can run
* `,createtemplate` - Create a template for your users to fill in
* `,deletetemplate` - Delete the template that your users can fill
* `,invite` - Get an invite link for the bot
* `,setNAME` - Sets a profile for the template NAME
* `,getNAME <@User>` - Gets a given profile for a user with profile NAME
* `,deleteNAME` - Deletes a profile for NAME; mods are able to run this on another user to delete *their* profile

# Why?

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
