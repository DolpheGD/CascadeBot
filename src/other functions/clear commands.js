const { REST, Routes } = require('discord.js');
const config = require('../config.json');

const rest = new REST({ version: '10' }).setToken(config.token);

(async () => {
    try {
        console.log('Started clearing global and guild commands.');

        // Delete all global commands
        const globalCommands = await rest.get(Routes.applicationCommands(config.clientId));
        for (const command of globalCommands) {
            await rest.delete(`${Routes.applicationCommands(config.clientId)}/${command.id}`);
        }

        // Delete all guild commands
        const guildCommands = await rest.get(Routes.applicationGuildCommands(config.clientId, config.guildId));
        for (const command of guildCommands) {
            await rest.delete(`${Routes.applicationGuildCommands(config.clientId, config.guildId)}/${command.id}`);
        }

        console.log('Successfully cleared all global and guild commands.');
    } catch (error) {
        console.error('Error clearing commands:', error);
    }
})();
