from datetime import datetime as dt
from json import load
from glob import glob
from re import compile as _compile
from logging import getLogger
from urllib.parse import urlencode

from aiohttp import ClientSession
from discord import Game, Message, Permissions
from discord.ext.commands import AutoShardedBot, when_mentioned_or

from cogs.utils.database import DatabaseConnection


LOGGER = getLogger('profilebot')


def get_prefix(bot, message:Message):
    '''
    Gives the prefix for the given guild
    '''

    return when_mentioned_or(*[','])(bot, message)


class CustomBot(AutoShardedBot):

    def __init__(self, config_file:str='config/config.json', commandline_args=None, *args, **kwargs):
        if kwargs.get('command_prefix'):
            super().__init__(*args, **kwargs)
        else:
            super().__init__(command_prefix=get_prefix, *args, **kwargs)

        # Store the config file for later
        self.config = None
        self.config_file = config_file
        self.reload_config()
        self.commandline_args = commandline_args

        # Allow database connections like this
        self.database = DatabaseConnection

        # Store the startup method so I can see if it completed successfully
        self.startup_time = dt.now()
        self.startup_method = None


    async def startup(self):
        '''
        Resets and fills the FamilyTreeMember cache with objects
        '''

        # Remove caches
        LOGGER.debug("Clearing caches")

        # Wait for the bot to cache users before continuing
        LOGGER.debug("Waiting until ready before completing startup method.")
        await self.wait_until_ready() 


    def get_extensions(self) -> list:
        '''Gets the filenames of all the loadable cogs'''

        ext = glob('cogs/[!_]*.py')
        rand = glob('cogs/utils/random_text/[!_]*.py')
        extensions = [i.replace('\\', '.').replace('/', '.')[:-3] for i in ext + rand]
        LOGGER.debug("Getting all extensions: " + str(extensions))
        return extensions


    def load_all_extensions(self):
        '''
        Loads all extensions from .get_extensions()
        '''

        LOGGER.debug('Unloading extensions... ')
        for i in self.get_extensions():
            log_string = f' * {i}... '
            try:
                self.unload_extension(i)
                log_string += 'sucess'
            except Exception as e:
                log_string += str(e)
            LOGGER.debug(log_string)
        LOGGER.debug('Loading extensions... ')
        for i in self.get_extensions():
            log_string = f' * {i}... '
            try:
                self.load_extension(i)
                log_string += 'sucess'
            except Exception as e:
                log_string += str(e)
            LOGGER.debug(log_string)


    async def set_default_presence(self):
        '''
        Sets the default presence of the bot as appears in the config file
        '''
        
        # Update presence
        LOGGER.debug("Setting default bot presence")
        presence_text = self.config['presence_text']
        if self.shard_count > 1:
            for i in range(self.shard_count):
                game = Game(f"{presence_text} (shard {i})")
                await self.change_presence(activity=game, shard_id=i)
        else:
            game = Game(presence_text)
            await self.change_presence(activity=game)


    def reload_config(self):
        LOGGER.debug("Reloading config")
        with open(self.config_file) as a:
            self.config = load(a)


    def run(self):
        super().run(self.config['token'])


    async def start(self, token:str=None):
        '''Starts up the bot and whathaveyou'''

        LOGGER.debug("Running startup method") 
        self.startup_method = self.loop.create_task(self.startup())
        LOGGER.debug("Running original D.py start method")
        await super().start(token or self.config['token'])

    
    async def logout(self):
        '''Logs out the bot and all of its started processes'''

        LOGGER.debug("Running original D.py logout method")
        await super().logout()
