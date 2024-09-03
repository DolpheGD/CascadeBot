// Bot by Dolphe
// TODO: Change all commands to await then edit reply. So far only done with chop, mine, explore, and forage







//
const fs = require('node:fs');
const path = require('node:path');
const { Client, Collection, Events, GatewayIntentBits } = require('discord.js');
const { token } = require('./config.json');

// Create a new client instance
const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent, // Required for accessing message content
        GatewayIntentBits.GuildMessageReactions,
    ]
});

// Command handler
client.commands = new Collection();

const foldersPath = path.join(__dirname, 'commands');
const commandFolders = fs.readdirSync(foldersPath);

for (const folder of commandFolders) {
    const commandsPath = path.join(foldersPath, folder);
    const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

    for (const file of commandFiles) {
        const filePath = path.join(commandsPath, file);
        const command = require(filePath);

        // Set a new item in the Collection with the key as the command name and the value as the exported module
        if ('data' in command && 'execute' in command) {
            client.commands.set(command.data.name, command);
        } else {
            console.log(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
        }
    }
}

// Event handler
const eventsPath = path.join(__dirname, 'events');
const eventFiles = fs.readdirSync(eventsPath).filter(file => file.endsWith('.js'));

for (const file of eventFiles) {
    const filePath = path.join(eventsPath, file);
    const event = require(filePath);
    if (event.once) {
        client.once(event.name, (...args) => event.execute(...args));
    } else {
        client.on(event.name, (...args) => event.execute(...args));
    }
}

// Global error handling
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    // Optionally, log to a file or notify the server owner here
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception thrown:', error);
    // Optionally, log to a file or notify the server owner here
    process.exit(1); // Restart the bot if necessary
});

// Graceful shutdown handling
process.on('SIGINT', () => {
    console.log('Shutting down gracefully...');
    client.destroy();
    process.exit(0);
});

// Database and Login Handling
const sequelize = require('./dbConfig');
const User = require('./models/User');
const Inventory = require('./models/Inventory'); // Ensure this path is correct

// Define associations
User.hasOne(Inventory, { foreignKey: 'userId' });
Inventory.belongsTo(User, { foreignKey: 'userId' });

async function initializeDatabase() {
    let retries = 5;
    while (retries) {
        try {
            await sequelize.sync();
            console.clear();
            console.log('Database synced');
            break;
        } catch (error) {
            console.error('Failed to sync database:', error);
            retries -= 1;
            console.log(`Retries left: ${retries}`);
            await new Promise(res => setTimeout(res, 5000)); // Wait 5 seconds before retrying
        }
    }

    if (!retries) {
        console.error('Could not connect to the database. Exiting.');
        process.exit(1);
    }
}

async function startBot() {
    try {
        await initializeDatabase();
        await client.login(token);
        console.log('Logged in to Discord');
    } catch (error) {
        console.error('Failed to start bot:', error);
        process.exit(1); // Exit if the bot fails to start
    }
}

startBot();
