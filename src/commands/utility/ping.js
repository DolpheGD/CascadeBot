const { SlashCommandBuilder } = require('discord.js');

module.exports = {
	data: new SlashCommandBuilder()
		.setName('ping')
		.setDescription('Verifies if the bot is online'),
	async execute(interaction) {
		await interaction.deferReply({ ephemeral: true });
		await interaction.editReply('Bot is online.');
	},
};