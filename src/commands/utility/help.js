const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
	data: new SlashCommandBuilder()
		.setName('help')
		.setDescription('Get a list of commands'),
	async execute(interaction) {
		await interaction.deferReply({ ephemeral: true });
		
		const embed = new EmbedBuilder()
        .setTitle(`**Command list:**`)
        .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
        .setColor('#0099ff')
		.addFields({ name: `\n**__Resource commands__**\n/chop`,
					value: `Gain wood and other resources`, inline: false })
		.addFields({ name: '/mine', value: `Gain stone and other resources`, inline: false })
		.addFields({ name: '/forage', value: `Gain berries, leaves, and other resources`, inline: false })
		.addFields({ name: '/fish', value: `Gain fish and other resources`, inline: false })
		.addFields({ name: '/explore', value: `Explore various events`, inline: false })

		.addFields({ name: `\n**__Automachine commands__**\n/builds view`,
					 value: `View your automachines`, inline: false })
		.addFields({ name: '/builds craft', value: `Craft an automachine`, inline: false })
		.addFields({ name: '/builds upgrade', value: `Upgrade an automachine`, inline: false })
		.addFields({ name: '/builds collect', value: `Collect from automachines`, inline: false })

		.addFields({ name: `\n**__Utility commands__**\n/daily`,
					 value: `Claim a daily reward`, inline: false })
		.addFields({ name: '/inv', value: `View your inventory`, inline: false })
		.addFields({ name: '/tools', value: `View your tools`, inline: false })
		.addFields({ name: '/leaderboard', value: `View the leaderboard`, inline: false })
		.addFields({ name: '/quest', value: `Claim a quest`, inline: false })

		.addFields({ name: `\n**__Bet commands__**\n/bet`,
					 value: `Bet resources`, inline: false })
		.addFields({ name: '/betall', value: `Bet all your resources`, inline: false });

		return interaction.editReply({embeds: [embed] });

	},
};