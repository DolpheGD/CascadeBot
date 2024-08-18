const { SlashCommandBuilder } = require('discord.js');

module.exports = {
	data: new SlashCommandBuilder()
		.setName('ping')
		.setDescription('Verifies if the bot is online'),
	async execute(interaction) {
		await interaction.reply('Bot is online.');
	},
};