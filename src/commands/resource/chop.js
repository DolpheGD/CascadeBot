const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool'); // Import Tool model

module.exports = {
    data: new SlashCommandBuilder()
        .setName('chop')
        .setDescription('Chop 3-6 wood with an axe or 1-5 wood without an axe'),

    async execute(interaction) {
        let cooldown = 20 * 1000; // 20 seconds cooldown
        const userId = interaction.user.id;
        const username = interaction.user.username;

        // Create or find the user and ensure the username is set
        const [user] = await User.findOrCreate({
            where: { discordId: userId },
            defaults: { username: username }
        });

        // Create or find the inventory
        const [inventory] = await Inventory.findOrCreate({
            where: { userId: user.id },
            defaults: { wood: 0, stone: 0, palmLeaves: 0, gold: 0, rope: 0 }
        });

        // Find the user's tools
        const tool = await Tool.findOne({ where: { userId: user.id } });

        const hasAxe = tool && tool.metalAxe && tool.metalAxeDurability > 0;

        if (hasAxe) {
            cooldown = 10 * 1000; // 10 seconds cooldown
        }

        const lastChop = user.lastChop || 0;
        const now = Date.now();

        if (now - lastChop < cooldown) {
            return interaction.reply({
                content: `You are chopping too fast! Please wait ${Math.ceil((cooldown - (now - lastChop)) / 1000)} more seconds.`,
                ephemeral: true
            });
        }

        let wood = hasAxe ? Math.floor(Math.random() * 4) + 3 : Math.floor(Math.random() * 5) + 1;
        inventory.wood += wood;

        let isNegative = false;
        let isBonus = false;
        let bonusWood = 0;
        let extraBonusWood = 0;
        let stolenWood = 0;
        let stolenLeaves = 0;
        let palmLeaves = 0;
        let rope = 0;

        if (hasAxe) { // check for axe durability
            tool.metalAxeDurability -= 1;

            if (tool.metalAxeDurability <= 0) {
                tool.metalAxe = false; // The axe breaks if durability reaches 0
                tool.metalAxeDurability = 0;
            }
            await tool.save();
        }

        if (Math.random() < 0.05) { // negative event 5%
            isNegative = true;
            if (Math.random() < 0.5) { 
                if (hasAxe) {
                    tool.metalAxeDurability -= 2; 
                    bonusWood = 4;
                    rope = 1;
                    inventory.wood += bonusWood;
                    inventory.rope += rope;
                } else {
                    stolenWood = Math.floor(Math.random() * 3) + 1;
                    inventory.wood -= stolenWood;
                }
            } else if (inventory.palmLeaves > 4) { 
                if (hasAxe) {
                    tool.metalAxeDurability -= 2; 
                    bonusWood = 4;
                    palmLeaves = 1;
                    inventory.wood += bonusWood;
                    inventory.palmLeaves += palmLeaves;
                } else {
                    stolenLeaves = Math.floor(Math.random() * 5) + 1;
                    inventory.palmLeaves -= stolenLeaves;
                }
            }
        } else {
            // extra stuff from axe
            if (Math.random() < (hasAxe ? 0.3 : 0.15)) { 
                isBonus = true;
                bonusWood = Math.floor(Math.random() * (hasAxe ? 5 : 3)) + 4;
                inventory.wood += bonusWood;
            }
            if (Math.random() < (hasAxe ? 0.65 : 0.5)) { 
                palmLeaves = Math.floor(Math.random() * 4) + 2;
                inventory.palmLeaves += palmLeaves;
            }
            if (Math.random() < (hasAxe ? 0.15 : 0.05)) { 
                rope += 1; 
                inventory.rope += rope;
            }
            if (hasAxe && Math.random() < 0.02) { 
                extraBonusWood = Math.floor(Math.random() * 16) + 15;
                inventory.wood += extraBonusWood;
            }
        }

        // Save the tool, inventory, and user data
        user.lastChop = now;
        await inventory.save();
        await user.save();

        const embed = new EmbedBuilder()
            .setColor(isNegative ? '#ff0000' : '#00ff00')
            .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
            .setTitle(
                (isNegative ? 'Failure!' : 'Success!') + (hasAxe ? ' [🪓]' : '')
            )
            .setDescription(isNegative
                ? `You angered ${rohanEvent ? 'Rohan' : 'Josh'}! **-${stolenLeaves || stolenWood}** ${rohanEvent ? '🍃' : '🪵'}.`
                : `You obtained ${wood} 🪵`)
            .setFooter({ text: `Total wood: ${inventory.wood}` });

        if (isBonus) {
            embed.addFields({ name: '**Bonus!**', value: `You chopped down a huge tree! **+${bonusWood}** 🪵!`, inline: false });
        }

        if (palmLeaves > 0) {
            embed.addFields({ name: '**Bonus!**', value: `You picked up some huge leaves! **+${palmLeaves}** 🍃!`, inline: false });
        }

        if (rope > 0) {
            embed.addFields({ name: '**Rare Bonus!**', value: `You found some leftover rope! **+${rope}** 🪢!`, inline: false });
        }

        if (hasAxe && extraBonusWood > 0) {
            embed.addFields({ name: '**🌳ULTRA Rare Bonus!🌳**', value: `You chopped down a humongous tree! **+${extraBonusWood}** 🪵!`, inline: false });
        }

        if (hasAxe && tool.metalAxeDurability === 0) {
            embed.addFields({ name: '**Axe Broken!**', value: `Your axe has broken!`, inline: false });
        }

        return interaction.reply({ embeds: [embed] });
    },
};
