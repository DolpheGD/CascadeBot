const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('mine')
        .setDescription('Mine for 2-4 stone'),

    async execute(interaction) {
        const cooldown = 30 * 1000; // 30 seconds cooldown
        const userId = interaction.user.id;

        try {
            // Find or create the user
            const [user] = await User.findOrCreate({
                where: { discordId: userId },
                defaults: {
                    username: interaction.user.username, // Set the username here
                }
            });

            // Find or create the inventory for the user
            const [inventory] = await Inventory.findOrCreate({
                where: { userId: user.id }, // Use user.id here
                defaults: {
                    wood: 0,
                    stone: 0,
                    palmLeaves: 0,
                    gold: 0,
                    copper: 0 // Add copper to the default inventory
                }
            });

            const lastMine = user.lastMine || 0;
            const now = Date.now();

            if (now - lastMine < cooldown) {
                return interaction.reply({
                    content: `You are mining too fast! Please wait ${Math.ceil((cooldown - (now - lastMine)) / 1000)} more seconds.`,
                    ephemeral: true
                });
            }

            let stone = Math.floor(Math.random() * 3) + 2; // Random amount of stone between 2 and 4
            let gold = Math.random() < 0.04 ? 1 : 0; // 4% chance of getting 1 gold
            let bonusStone = Math.random() < 0.25 ? Math.floor(Math.random() * 3) + 2 : 0; // 25% chance of getting a bonus of 2-4 stone
            let copper = Math.random() < 0.2 ? Math.floor(Math.random() * 3) + 1 : 0; // 20% chance of getting 1-3 copper
            let hugeCopperVein = Math.random() < 0.03 ? Math.floor(Math.random() * 4) + 5 : 0; // 3% chance of getting 5-8 copper

            // Negative events
            const negativeEventChance = Math.random();
            if (negativeEventChance < 0.1) { // 10% chance for negative events

                if (inventory.stone > 3 && Math.random() < 0.8) { // 80% of the negative events being stone theft
                    const stoneLost = Math.floor(Math.random() * 3) + 1;
                    inventory.stone = Math.max(inventory.stone - stoneLost, 0); // Ensure stone doesn't go below 0
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Oh No!')
                        .setDescription(`You bump into Josh in the mines and he steals some stone from you!\n**-${stoneLost}** 🪨`)
                        .setFooter({ text: `Total stone: ${inventory.stone}` });

                    return interaction.reply({ embeds: [embed] });

                } else if (inventory.gold > 1) { // The other 20% of negative events being gold theft
                    const goldLost = Math.floor(Math.random() * 2) + 1;
                    inventory.gold = Math.max(inventory.gold - goldLost, 0); // Ensure gold doesn't go below 0
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Oh No!')
                        .setDescription(`You find Rohan, who is jealous of your gold and attacks you!\n**-${goldLost}** ✨`)
                        .setFooter({ text: `Total gold: ${inventory.gold}` });

                    return interaction.reply({ embeds: [embed] });
                }
            }

            // Update inventory with mined resources and possible bonus
            inventory.stone += stone + bonusStone;
            inventory.gold += gold;
            inventory.copper += copper + hugeCopperVein;
            user.lastMine = now;

            // Save the inventory and user cooldown
            await inventory.save();
            await user.save();

            const embed = new EmbedBuilder()
                .setColor('#00ff00')
                .setTitle('Success!')
                .setDescription(`You obtained ${stone} 🪨`)
                .setFooter({ text: `Total stone: ${inventory.stone}` });

            if (bonusStone > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined extra stone!\n**+${bonusStone}** 🪨`, inline: false });
            }

            if (copper > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined some copper!\n**+${copper}** 🔶`, inline: false });
            }

            if (gold > 0) {
                embed.addFields({ name: 'Rare Bonus!', value: `You mined something shiny!\n**+${gold}** ✨`, inline: false });
            }

            if (hugeCopperVein > 0) {
                embed.addFields({ name: 'Rare Bonus!', value: `You struck a huge copper vein!\n**+${hugeCopperVein}** 🔶`, inline: false });
            }

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error mining stone:', error);
            return interaction.reply({ content: 'An error occurred while mining. Please try again later.', ephemeral: true });
        }
    },
};
