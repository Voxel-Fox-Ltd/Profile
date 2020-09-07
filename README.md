# Profile

Profile is a powerful Discord bot used to help handle storing for your servers. 

## What does it do?

With Profile, your server's moderators are able to create, modify, and manage different forms for users to fill in. Systems like this are a great help to a variety of communities - from storing character information on roleplay servers to storing your fantasy football team.

![A Discord embed showing the information of a character](https://voxelfox.co.uk/static/images/profile/new/created_profile.png)

Using Profile gives you automated flexibility - if a user responds a certain way, you can automatically assign them a role. Profiles can automatically fill in values based on current user roles. Profiles can be set to be verified before they're public. And more.

## How do I use it?

All of the bot's commands are available to you if you run `,help` (the prefix is changable, but defaults to `,`). I'll list them here for reference as well, though.

For these command examples, I'll assume you're trying to create and use a template called "character"

![A gif showing the template and profile setup process](https://voxelfox.co.uk/static/images/profile/new/template_and_profile_creation.gif)

### Managing templates

Only users with the `manage roles` permission are able to run these commands.

* `,createtemplate Character`
    * This will create a new template that users can fill in
* `,edittemplate Character`
    * This will allow you to edit values of the template. From the edit menu, you can add new fields, delete old ones, change the verification channel, roles, etc.
* `,deletetemplate Character`
    * This will permanently delete the `Character` template, and all associated profiles. This action is irreversible.
* `,templates`
    * This will list the templates for your server.

### Managing profiles

* `,setcharacter`
    * This will set up a profile for the `Character` template on your server.
* `,getcharacter [@User#0001]`
    * This will get the `Character` profile for a given user.
    * If the user has multiple profiles, you can pick which one you want to see by just giving its name.
* `,editcharacter`
    * This will edit your `Character` profile.
* `,deletecharacter`
    * This will delete your `Character` profile.
