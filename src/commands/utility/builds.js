const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const AutoMachine = require('../../models/AutoMachine');
const Inventory = require('../../models/Inventory');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('builds')
        .setDescription('Manage your automachines.')
        .addSubcommand(subcommand =>
            subcommand
                .setName('view')
                .setDescription('View your automachines and stored resources.'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('craft')
                .setDescription('Craft an automachine.'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('upgrade')
                .setDescription('Upgrade an automachine.'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('collect')
                .setDescription('Collect from your automachines.')),

    async execute(interaction) {
        await interaction.deferReply();
        
        const discordId = interaction.user.id;
        const subcommand = interaction.options.getSubcommand();
        
        // Fetch user from the database using their Discord ID
        const user = await User.findOne({ where: { discordId } });

        if (!user) {
            return interaction.editReply({ content: 'User not found.', ephemeral: true });
        }

        const userId = user.id; // Get the user ID from the User model

        if (subcommand === 'view') {
            await viewBuilds(interaction, userId);
        } else if (subcommand === 'craft') {
            await craftAutoMachine(interaction, userId);
        } else if (subcommand === 'upgrade') {
            await upgradeAutoMachine(interaction, userId);
        } else if (subcommand === 'collect') {
            await collectAutoMachineResources(interaction, userId);
        }
    },
};






// -----------------------------------
// Function to view automachines and resources
// -----------------------------------
async function viewBuilds(interaction, userId) {
    const MAX_LEVEL = 6;
    const machines = await AutoMachine.findAll({ where: { userId } });

    // Check if the user doesn't have any machines, create a default entry
    if (machines.length === 0) {
        await AutoMachine.create({ userId, type: 'autochopper', wood: 0, rope: 0, upgradeLevel: 0 });
    }

    // Create a map of owned machines for easy access
    const machineMap = {};
    machines.forEach(machine => {
        machineMap[machine.type] = machine;
    });

    const embed = new EmbedBuilder()
        .setTitle(`${interaction.user.username}'s Automachines`)
        .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
        .setColor('#0099ff');

    // Autochopper
    if (machineMap['autochopper']) {
        const autochopper = machineMap['autochopper'];
        embed.addFields({
            name: `🤖🪓 Autochopper [Lvl ${autochopper.upgradeLevel + 1}/${MAX_LEVEL}] ${10 + 2 * autochopper.upgradeLevel}🪵/hr ${1 + autochopper.upgradeLevel}🪢/hr`,
            value: `Wood: ${autochopper.wood}/${200 + 20 * autochopper.upgradeLevel}\nRope: ${autochopper.rope}/${10 + 4 * autochopper.upgradeLevel}`,
        });
    } else {
        embed.addFields({
            name: '🤖🪓 Autochopper',
            value: 'Not owned',
        });
    }

    // Autominer
    if (machineMap['autominer']) {
        const autominer = machineMap['autominer'];
        embed.addFields({
            name: `🤖⛏️ Autominer [Lvl ${autominer.upgradeLevel + 1}/${MAX_LEVEL}] ${10 + 2 * autominer.upgradeLevel}🪨/hr ${5 + 2 * autominer.upgradeLevel}🔶/hr`,
            value: `Stone: ${autominer.stone}/${200 + 20 * autominer.upgradeLevel}\nCopper: ${autominer.copper}/${100 + 10 * autominer.upgradeLevel}`,
        });
    } else {
        embed.addFields({
            name: '🤖⛏️ Autominer',
            value: 'Not owned',
        });
    }

    // Autoforager
    if (machineMap['autoforager']) {
        const autoforager = machineMap['autoforager'];
        embed.addFields({
            name: `🤖🌿 Autoforager [Lvl ${autoforager.upgradeLevel + 1}/${MAX_LEVEL}] ${5 + 2 * autoforager.upgradeLevel}🍃/hr ${5 + 2 * autoforager.upgradeLevel}🫐/hr ${2 + autoforager.upgradeLevel}🍎/hr`,
            value: `Palm Leaves: ${autoforager.palmLeaves}/${100 + 10 * autoforager.upgradeLevel}\nBerries: ${autoforager.berries}/${100 + 10 * autoforager.upgradeLevel}\nApples: ${autoforager.apples}/${20 + 4 * autoforager.upgradeLevel}`,
        });
    } else {
        embed.addFields({
            name: '🤖🌿 Autoforager',
            value: 'Not owned',
        });
    }

    return interaction.editReply({ embeds: [embed] });
}




// -----------------------------------
// Function to craft automachines
// -----------------------------------
async function craftAutoMachine(interaction, userId) {
    const user = await User.findOne({ where: { id: userId } });
    const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });
    const machines = await AutoMachine.findAll({ where: { userId } });
    const machineMap = {};
    
    machines.forEach(machine => {
        machineMap[machine.type] = machine;
    });


    if (!user) {
        return interaction.editReply({ content: 'User not found.', ephemeral: true });
    }

    // DFescription
    let desc = "";

    if (!machineMap['autochopper']){
        desc += `🤖🪓**Autochopper**\xa0\xa0\xa0 -1🔋 -15⚙️ -1💎 -15♦️ -100🪵\n`;
    }else{
        desc += `🤖🪓**Autochopper**\xa0\xa0\xa0 Owned!\n`;
    }

    if (!machineMap['autominer']) {
        desc += `🤖⛏️**Autominer**\xa0\xa0\xa0 -1🔋 -15⚙️ -1💎 -15♦️ -100🪨\n`;
    }else{
        desc += `🤖⛏️**Autominer**\xa0\xa0\xa0 Owned!\n`;
    }

    if (!machineMap['autoforager']){
        desc += `🤖🌿**Autoforager**\xa0\xa0\xa0 -1🔋 -15⚙️ -1💎 -15♦️ -100🌿\n`;
    }else{
        desc += `🤖🌿**Autoforager**\xa0\xa0\xa0 Owned!\n`;
    }


    const craftmenu = new EmbedBuilder()
        .setTitle(`${interaction.user.username}'s Automachines - Craft`)
        .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
        .setColor('#0099ff')
        .setDescription(desc);
    
    const row = new ActionRowBuilder()
        .addComponents(
            new ButtonBuilder()
                .setCustomId('craft_autochopper')
                .setLabel('Autochopper')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('craft_autominer')
                .setLabel('Autominer')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('craft_autoforager')
                .setLabel('Autoforager')
                .setStyle(ButtonStyle.Primary)
        );

    await interaction.editReply({ embeds: [craftmenu], components: [row] });

    const filter = i => i.user.id === interaction.user.id;
    const collector = interaction.channel.createMessageComponentCollector({ filter, time: 30000 });

    collector.on('collect', async i => {

        if (i.customId === 'craft_autochopper') {
            if (machineMap['autochopper']){ // already own error
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You already own an autochopper')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }
            
            // not enough mat error
            if (inventory.negadomBattery < 1 || inventory.metalParts < 15 || inventory.diamond < 1 || inventory.ruby < 15 || inventory.wood < 100) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You do not have enough materials to craft an Autochopper.')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.negadomBattery -= 1;
            inventory.metalParts -= 15;
            inventory.diamond -= 1;
            inventory.ruby -= 15;
            inventory.wood -= 100;

            await AutoMachine.create({ userId: user.id, type: 'autochopper', wood: 0, rope: 0, upgradeLevel: 0 });
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Crafting Success')
                .setDescription('You have successfully crafted an Autochopper!')
                .setColor('#00FF00');
            await i.editReply({ embeds: [successEmbed] });

        } else if (i.customId === 'craft_autominer') {
            if (machineMap['autominer']){ // already own error
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You already own an autominer')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }

            // error
            if (inventory.negadomBattery < 1 || inventory.metalParts < 15 || inventory.diamond < 1 || inventory.ruby < 15 || inventory.stone < 100) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You do not have enough materials to craft an Autominer.')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.negadomBattery -= 1;
            inventory.metalParts -= 15;
            inventory.diamond -= 1;
            inventory.ruby -= 15;
            inventory.stone -= 100;

            await AutoMachine.create({ userId: user.id, type: 'autominer', wood: 0, rope: 0, upgradeLevel: 0 });
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Crafting Success')
                .setDescription('You have successfully crafted an Autominer!')
                .setColor('#00FF00');
            await i.editReply({ embeds: [successEmbed] });
            
        } else if (i.customId === 'craft_autoforager') {
            if (machineMap['autoforager']){ // already own error
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You already own an autoforager')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }

            if (inventory.negadomBattery < 1 || inventory.metalParts < 15 || inventory.diamond < 1 || inventory.ruby < 15 || inventory.palmLeaves < 100) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Crafting Error')
                    .setDescription('You do not have enough materials to craft an Autoforager.')
                    .setColor('#FF0000');
                return i.editReply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.negadomBattery -= 1;
            inventory.metalParts -= 15;
            inventory.diamond -= 1;
            inventory.ruby -= 15;
            inventory.palmLeaves -= 100;

            await AutoMachine.create({ userId: user.id, type: 'autoforager', wood: 0, rope: 0, upgradeLevel: 0 });
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Crafting Success')
                .setDescription('You have successfully crafted an Autoforager!')
                .setColor('#00FF00');
            await i.editReply({ embeds: [successEmbed] });
        }

        collector.stop();
    });

    collector.on('end', collected => {
        if (collected.size === 0) {
            const timeoutEmbed = new EmbedBuilder()
                .setTitle('Crafting Timeout')
                .setDescription('You took too long to select an option.')
                .setColor('#FF0000');
            interaction.editReply({ embeds: [timeoutEmbed], components: [] });
        }
    });
}




// -----------------------------------
// Function to upgrade an automachine
// -----------------------------------
async function upgradeAutoMachine(interaction, userId) {
    const user = await User.findOne({ where: { id: userId } });
    const machines = await AutoMachine.findAll({ where: { userId } });
    const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

    const machineMap = {};
    machines.forEach(machine => {
        machineMap[machine.type] = machine;
    });

    const MAX_LEVEL = 6;
    
    if (!user) {
        return interaction.editReply({ content: 'User not found.', ephemeral: true });
    }

    // Description
    let desc = "";

    if (!machineMap['autochopper']){
        desc += `🤖🪓**Autochopper** \xa0 Not owned\n`;
    }else{
        const autochopper = machineMap['autochopper'];
        desc += `🤖🪓**Autochopper** [Lvl ${autochopper.upgradeLevel + 1}/${MAX_LEVEL}] \xa0 -20⚙️ -200🔶 -100🪵\n`;
    }
    
    if (!machineMap['autominer']) {
        desc += `🤖⛏️**Autominer** \xa0 Not owned\n`;
    }else{
        const autominer = machineMap['autominer'];
        desc += `🤖⛏️**Autominer** [Lvl ${autominer.upgradeLevel + 1}/${MAX_LEVEL}] \xa0 -20⚙️ -200🔶 -100🪨\n`;
    }
    
    if (!machineMap['autoforager']){
        desc += `🤖🌿**Autoforager** \xa0 Not owned\n`;
    }else{
        const autoforager = machineMap['autoforager'];
        desc += `🤖🌿**Autoforager** [Lvl ${autoforager.upgradeLevel + 1}/${MAX_LEVEL}] \xa0 -20⚙️ -200🔶 -100🫐\n`;
    }
    
    
    const craftmenu = new EmbedBuilder()
        .setTitle(`${interaction.user.username}'s Automachines - Craft`)
        .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
        .setColor('#0099ff')
        .setDescription(desc);

    const row = new ActionRowBuilder()
        .addComponents(
            new ButtonBuilder()
                .setCustomId('upgrade_autochopper')
                .setLabel('Upgrade Autochopper')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('upgrade_autominer')
                .setLabel('Upgrade Autominer')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('upgrade_autoforager')
                .setLabel('Upgrade Autoforager')
                .setStyle(ButtonStyle.Primary)
        );

    await interaction.editReply({ embeds: [craftmenu], components: [row] });

    const filter = i => i.user.id === interaction.user.id;
    const collector = interaction.channel.createMessageComponentCollector({ filter, time: 30000 });

    collector.on('collect', async i => {
        // AUTOCHOPPER
        if (i.customId === 'upgrade_autochopper') {
            const autochopper = machines.find(machine => machine.type === 'autochopper');

            if (!autochopper) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not own an Autochopper to upgrade.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }
            if (autochopper.upgradeLevel + 1 >= MAX_LEVEL){
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription(`You already upgraded to the max level (${MAX_LEVEL})`)
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });  
            }

            // Example upgrade costs; adjust as necessary
            if (inventory.metalParts < 20 || inventory.wood < 100 || inventory.copper < 200) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not have enough resources to upgrade the Autochopper.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.metalParts -= 20;
            inventory.wood -= 100;
            inventory.copper -= 200;
            autochopper.upgradeLevel += 1;
            await autochopper.save();
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Upgrade Success')
                .setDescription('Your Autochopper has been upgraded!')
                .setColor('#00FF00');
            await i.reply({ embeds: [successEmbed] });

        // AUTOMINER
        } else if (i.customId === 'upgrade_autominer') {
            const autominer = machines.find(machine => machine.type === 'autominer');

            if (!autominer) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not own an Autominer to upgrade.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }
            if (autominer.upgradeLevel + 1 >= MAX_LEVEL){
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription(`You already upgraded to the max level (${MAX_LEVEL})`)
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });  
            }

            // Example upgrade costs; adjust as necessary
            if (inventory.metalParts < 20 || inventory.stone < 100 || inventory.copper < 200) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not have enough resources to upgrade the Autominer.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.metalParts -= 20;
            inventory.stone -= 100;
            inventory.copper -= 200;
            autominer.upgradeLevel += 1;
            await autominer.save();
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Upgrade Success')
                .setDescription('Your Autominer has been upgraded!')
                .setColor('#00FF00');
            await i.reply({ embeds: [successEmbed] });
        
        //AUTOFORAGER
        } else if (i.customId === 'upgrade_autoforager') {
            const autoforager = machines.find(machine => machine.type === 'autoforager');

            if (!autoforager) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not own an Autoforager to upgrade.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }
            if (autoforager.upgradeLevel + 1 >= MAX_LEVEL){
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription(`You already upgraded to the max level (${MAX_LEVEL})`)
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });  
            }

            // Example upgrade costs; adjust as necessary
            if (inventory.metalParts < 20 || inventory.berries < 100 || inventory.copper < 200) {
                const errorEmbed = new EmbedBuilder()
                    .setTitle('Upgrade Error')
                    .setDescription('You do not have enough resources to upgrade the Autoforager.')
                    .setColor('#FF0000');
                return i.reply({ embeds: [errorEmbed], ephemeral: true });
            }

            inventory.metalParts -= 20;
            inventory.berries -= 100;
            inventory.copper -= 200;
            autoforager.upgradeLevel += 1;
            await autoforager.save();
            await user.save();
            await inventory.save();
            const successEmbed = new EmbedBuilder()
                .setTitle('Upgrade Success')
                .setDescription('Your Autoforager has been upgraded!')
                .setColor('#00FF00');
            await i.reply({ embeds: [successEmbed] });
        }

        collector.stop();
    });

    collector.on('end', collected => {
        if (collected.size === 0) {
            const timeoutEmbed = new EmbedBuilder()
                .setTitle('Upgrade Timeout')
                .setDescription('You took too long to select an option.')
                .setColor('#FF0000');
            interaction.editReply({ embeds: [timeoutEmbed], components: [] });
        }
    });
}




// -----------------------------------
// Function to collect resources from automachines
// -----------------------------------
async function collectAutoMachineResources(interaction, userId) {
    try {
        // Fetch user's automachines
        const machines = await AutoMachine.findAll({ where: { userId } });
        if (!machines || machines.length === 0) {
            return interaction.editReply({ content: 'You do not own any automachines.', ephemeral: true });
        }

        // Fetch user's inventory
        let inventory = await Inventory.findOne({ where: { userId } });
        if (!inventory) {
            return interaction.editReply({ content: 'Your inventory could not be found.', ephemeral: true });
        }

        // Initialize variables to hold total collected resources
        let totalWood = 0;
        let totalStone = 0;
        let totalCopper = 0;
        let totalPalmLeaves = 0;
        let totalRope = 0;
        let totalBerries = 0;
        let totalApples = 0;

        // Iterate over machines and sum up resources
        machines.forEach(machine => {
            if (machine.type === 'autochopper') {
                totalWood += machine.wood;
                totalRope += machine.rope;
                machine.wood = 0; // Reset resources after collection
                machine.rope = 0;
            } else if (machine.type === 'autominer') {
                totalStone += machine.stone;
                totalCopper += machine.copper;
                machine.stone = 0;
                machine.copper = 0;
            } else if (machine.type === 'autoforager') {
                totalBerries += machine.berries;
                totalApples += machine.apples;
                totalPalmLeaves += machine.palmLeaves;
                machine.berries = 0;
                machine.palmLeaves = 0;
                machine.apples = 0;
            }
        });

        // Update user's inventory with collected resources
        inventory.wood += totalWood;
        inventory.stone += totalStone;
        inventory.copper += totalCopper;
        inventory.palmLeaves += totalPalmLeaves;
        inventory.rope += totalRope;
        inventory.berries += totalBerries;
        inventory.apples += totalApples;

        // Save updated inventory and reset automachines
        await inventory.save();
        await Promise.all(machines.map(machine => machine.save()));

        // Build an embed message
        const embed = new EmbedBuilder()
            .setTitle(`${interaction.user.username}'s AutoMachine Collection`)
            .setColor('#00FF00')
            .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }));

        // Conditionally add fields if any resources were collected
        if (totalWood > 0) embed.addFields({ name: 'Wood Collected', value: `${totalWood} 🪵`, inline: true });
        if (totalStone > 0) embed.addFields({ name: 'Stone Collected', value: `${totalStone} 🪨`, inline: true });
        if (totalCopper > 0) embed.addFields({ name: 'Copper Collected', value: `${totalCopper} 🔶`, inline: true });
        if (totalPalmLeaves > 0) embed.addFields({ name: 'Palm Leaves Collected', value: `${totalPalmLeaves} 🍃`, inline: true });
        if (totalRope > 0) embed.addFields({ name: 'Rope Collected', value: `${totalRope} 🪢`, inline: true });
        if (totalBerries > 0) embed.addFields({ name: 'Berries Collected', value: `${totalBerries} 🫐`, inline: true });
        if (totalApples > 0) embed.addFields({ name: 'Apples Collected', value: `${totalApples} 🍎`, inline: true });

        // Check if no resources were collected
        if (totalWood === 0 && totalStone === 0 && totalCopper === 0 && totalPalmLeaves === 0 && totalRope === 0 && totalBerries === 0 && totalApples === 0) {
            embed.setDescription('No resources were collected from your automachines.');
        }

        // Reply with the embed message
        return interaction.editReply({ embeds: [embed] });

    } catch (error) {
        console.error('Error collecting resources:', error);
        return interaction.editReply({ content: 'An error occurred while collecting resources. Please try again later.', ephemeral: true });
    }
}
