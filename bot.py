from argparse import ArgumentParser
from warnings import filterwarnings
import logging

from discord import Game, Status

from cogs.utils.custom_bot import CustomBot
from cogs.utils.database import DatabaseConnection
from cogs.utils.redis import RedisConnection


# Set up loggers
logging.basicConfig(format='%(name)s:%(levelname)s: %(message)s')
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('profilebot.db').setLevel(logging.INFO)
logger = logging.getLogger('profilebot')
logger.setLevel(logging.DEBUG)

# Filter warnings
filterwarnings('ignore', category=RuntimeWarning)

# Parse arguments
parser = ArgumentParser()
parser.add_argument("config_file", help="The configuration for the bot.")
parser.add_argument("--min", type=int, default=None, help="The minimum shard ID that this instance will run with (inclusive)")
parser.add_argument("--max", type=int, default=None, help="The maximum shard ID that this instance will run with (inclusive)")
parser.add_argument("--shardcount", type=int, default=None, help="The amount of shards that the bot should be using.")
args = parser.parse_args()

# Create bot object
shard_ids = None if args.shardcount == None else list(range(args.min, args.max+1))
if args.shardcount == None and (args.min or args.max):
    raise Exception("You set a min/max shard handler but no shard count")
bot = CustomBot(
    config_file=args.config_file,
    activity=Game(name="Reconnecting..."),
    status=Status.dnd,
    case_insensitive=True,
    shard_count=args.shardcount,
    shard_ids=shard_ids,
    shard_id=args.min,
)


@bot.event
async def on_ready():
    '''
    Runs when the bot is connected to the Discord servers
    Method is used to set the presence and load cogs
    '''

    logger.info('Bot connected:')
    logger.info(f'\t{bot.user}')
    logger.info(f'\t{bot.user.id}')
    
    logger.info("Setting activity to default")
    await bot.set_default_presence()
    logger.info('Bot loaded.')


if __name__ == '__main__':
    '''
    Starts the bot (and webserver if specified) and runs forever
    '''

    # Grab the event loop
    loop = bot.loop

    # Connect the database
    logger.info("Creating database pool")
    try:
        loop.run_until_complete(DatabaseConnection.create_pool(bot.config['database']))
    except Exception as e:
        logger.error("Error creating database pool")
        raise e

    # Connect the redis
    logger.info("Creating redis pool")
    try:
        loop.run_until_complete(RedisConnection.create_pool(bot.config['redis']))
    except Exception as e:
        logger.error("Error creating Redis pool")

    # Load the bot's extensions
    logger.info('Loading extensions... ')
    bot.load_all_extensions()

    # Run the bot
    try:
        logger.info("Running bot")
        bot.run()
    except KeyboardInterrupt: 
        pass

    # We're now done running the bot, time to clean up and close
    logger.info("Closing database pool")
    loop.run_until_complete(DatabaseConnection.pool.close())
    logger.info("Closing redis pool")
    loop.run_until_complete(RedisConnection.pool.close())
    logger.info("Closing asyncio loop")
    loop.close()
