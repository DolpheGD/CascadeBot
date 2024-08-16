const { SlashCommandBuilder } = require('discord.js');

module.exports = {
	data: new SlashCommandBuilder()
		.setName('ping')
		.setDescription('Calls you a hater'),
	async execute(interaction) {
		await interaction.reply('...Dam hater');
	},
};