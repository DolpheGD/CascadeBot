const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool'); // Adjust the path as needed
const tools = require('../utility/tools');

const resourceEmojiMap = {
    wood: '🪵',
    stone: '🪨',
    palmLeaves: '🍃',
    copper: '🔶',
    rope: '🪢',
    gold: '✨',
    ruby: '♦️'
};







//------------------------------------------------
// EVENTS
//------------------------------------------------
const events = [
    {
        id: 1,
        description: "You spot Josh near a campfire",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Ambush Josh',
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (chance < 0.4) { // 40% chance for ambush
                        let resourceFound = false;
                        resultMessage = 'Josh beats you up and steals your resources!\n';
    
                        while (!resourceFound) {
                            const resources = ['wood', 'stone', 'palmLeaves'];
                            const resource = resources[Math.floor(Math.random() * resources.length)];
                            const amount = Math.floor(Math.random() * 5) + 1; // 1 to 5
    
                            if (inventory[resource] >= amount) {
                                inventory[resource] -= amount;
                                await inventory.save();
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                                resourceFound = true;
                            }
    
                            if (resources.every(r => inventory[r] < 1)) {
                                resultMessage = 'Josh ambushes you but you don\'t have enough resources to lose.';
                                resourceFound = true;
                            }
                        }
                        embedColor = '#ff0000'; // Red color for ambush
                    } else {
                        const woodGained = Math.floor(Math.random() * 4) + 3;
                        inventory.wood += woodGained;
                        await inventory.save();
                        resultMessage = `You ambush Josh and he flees! You collect the leftover wood.\n**+${woodGained}** 🪵`;
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Barter 2✨ for wood',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.gold >= 2) {
                        inventory.gold -= 2;
                        const chance = Math.random();
    
                        if (chance < 0.95) { // 95% chance of getting wood
                            const woodGained = Math.floor(Math.random() * 8) + 5; // 5 to 12 wood
                            inventory.wood += woodGained;
                            resultMessage = `Josh accepts your gold and gives you some spare wood!\n**+${woodGained}** 🪵`;
                        } else { // 5% chance of getting scammed
                            resultMessage = 'Josh takes your gold and runs away!';
                            embedColor = '#ff0000'; // Red color for scam
                        }
                    } else {
                        resultMessage = 'You don’t have enough gold to barter!';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Barter 2♦️ for wood',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        const chance = Math.random();
    
                        if (chance < 0.98) { // 98% chance of getting a huge stack of wood
                            const woodGained = Math.floor(Math.random() * 61) + 50; // 50 to 110 wood
                            inventory.wood += woodGained;
                            resultMessage = `Josh accepts your rubies and gives you a huge stack of wood!\n**+${woodGained}** 🪵`;
                        } else { // 2% chance of getting scammed
                            resultMessage = 'Josh takes your rubies and runs away!';
                            embedColor = '#ff0000'; // Red color for scam
                        }
                    } else {
                        resultMessage = 'You don’t have enough rubies to barter!';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Leave',
                result: () => ({ message: 'You run away!', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275352717501665332/JOSHCAMPFIRE_1.png?ex=66c59446&is=66c442c6&hm=ab921b1d1c60330420fb37749ee9e02ecd2902672ea3cc5b4bdd230706dee121&'
    },
    {
        id: 2,
        description: "You spot a homeless Dolphe on the sidewalk.",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Donate 5🪵',
                result: async (interaction, inventory) => {
                    return await handleDolpheDonation(interaction, inventory, 'wood', '🪵');
                }
            },
            {
                emoji: '2️⃣',
                text: 'Donate 5🪨',
                result: async (interaction, inventory) => {
                    return await handleDolpheDonation(interaction, inventory, 'stone', '🪨');
                }
            },
            {
                emoji: '3️⃣',
                text: 'Donate 5🌿',
                result: async (interaction, inventory) => {
                    return await handleDolpheDonation(interaction, inventory, 'palmLeaves', '🌿');
                }
            },
            {
                emoji: '4️⃣',
                text: 'Donate 5🔶',
                result: async (interaction, inventory) => {
                    return await handleDolpheDonation(interaction, inventory, 'copper', '🔶');
                }
            },
            {
                emoji: '5️⃣',
                text: 'Donate nothing!!',
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
    
                    if (chance < 0.5) {
                        resultMessage = 'Dolphe looks at you with a pitiful stare.';
                    } else {
                        const resourcesLost = {
                            wood: Math.min(1, inventory.wood),
                            stone: Math.min(1, inventory.stone),
                            palmLeaves: Math.min(1, inventory.palmLeaves),
                            copper: Math.min(1, inventory.copper)
                        };
    
                        if (resourcesLost.wood > 0 || resourcesLost.stone > 0 || resourcesLost.palmLeaves > 0 || resourcesLost.copper > 0) {
                            resultMessage = `Dolphe attacks you for your resources! You lose:\n` +
                                            `**-${resourcesLost.wood}** 🪵\n` +
                                            `**-${resourcesLost.stone}** 🪨\n` +
                                            `**-${resourcesLost.palmLeaves}** 🌿\n` +
                                            `**-${resourcesLost.copper}** 🔶`;
    
                            inventory.wood -= resourcesLost.wood;
                            inventory.stone -= resourcesLost.stone;
                            inventory.palmLeaves -= resourcesLost.palmLeaves;
                            inventory.copper -= resourcesLost.copper;
                            await inventory.save();
                        } else {
                            resultMessage = 'Dolphe tries to attack you, but you have no resources to lose!';
                        }
                    }
    
                    return { message: resultMessage, color: '#ff0000' }; // Red color for attack
                }
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275348918305161216/HOMELESSDOLPHE.png?ex=66c590bc&is=66c43f3c&hm=91d0541edbb46f3b392800d8cc055eb7d62d56367f61c9d964b47f36f2a5292b&' 
    },
    {
        id: 3,
        description: "You come across Xender, a shady businessman\n\n[NOT SCAM Lottery] 1🪵 1🪨 1🌿 1🔶 for a chance to win 10✨\n\n[SUPER NOT SCAM Lottery] 10✨ for a chance to win 1💎\n",
        choices: [
            { emoji: '1️⃣', text: 'Enter NOT SCAM lottery', result: async (interaction, inventory) => {
                if (inventory.wood >= 1 && inventory.stone >= 1 && inventory.palmLeaves >= 1 && inventory.copper >= 1 ) {
                    inventory.wood -= 1;
                    inventory.stone -= 1;
                    inventory.palmLeaves -= 1;
                    inventory.copper -= 1;
                    await inventory.save();

                    const winChance = Math.random();
                    let resultMessage = '[NOT SCAM lottery]';

                    if (winChance < 0.1) { // 10% chance to win 10 gold
                        inventory.gold += 10;
                        await inventory.save();
                        resultMessage += '\nCongratulations! You won!\n**+10**✨';
                        return { message: resultMessage, color: '#00ff00' }; // Green color for winning
                    } else {
                        resultMessage += '\nSorry, you got scammed';
                        return { message: resultMessage, color: '#ff0000' }; // Red color for losing
                    }
                } else {
                    return { message: 'You do not have enough resources to accept the deal.', color: '#ff0000' }; // Red color for insufficient resources
                }
            }},
            { emoji: '2️⃣', text: '[SUPER NOT SCAM lottery]', result: async (interaction, inventory) => {
                if (inventory.gold >= 10) {
                    inventory.gold -= 10;
                    await inventory.save();

                    const winChance = Math.random();
                    let resultMessage = 'You entered the SUPER NOT SCAM lottery';

                    if (winChance < 0.05) { // 5% chance to win 1 diamond
                        inventory.diamond += 1;
                        await inventory.save();
                        resultMessage += '\nNo way! You actually won!\n**+1**💎';
                        return { message: resultMessage, color: '#00ff00' }; // Green color for winning
                    } else {
                        resultMessage += '\nSorry, you got SUPER scammed';
                        return { message: resultMessage, color: '#ff0000' }; // Red color for losing
                    }
                } else {
                    return { message: 'You do not have enough resources to accept the deal.', color: '#ff0000' }; // Red color for insufficient resources
                }
            }},
            { emoji: '3️⃣', text: 'Leave', result: () => ({ message: 'You leave Xender and continue your exploration.', color: '#0099ff' })}
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275340818382721024/XENDERCRACKPIPE_1.png?ex=66c58931&is=66c437b1&hm=80d6a37f392521c4d15142e9cabe0ee42097f54c98f0469517305a0378d1dabe&'
    },
    {
        id: 4,
        description: "You meet Rex, an old crafter. He offers to craft your palm leaves into rope.",
        choices: [
            { 
                emoji: '1️⃣', 
                text: 'Craft 4🌿 into 2🪢', 
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 4) {
                        inventory.palmLeaves -= 4;
                        inventory.rope = (inventory.rope || 0) + 2;
                        await inventory.save();
                        return { message: 'Rex crafts rope for you!\n**+2**🪢', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves!', color: '#ff0000' };
                    }
                }
            },
            { 
                emoji: '2️⃣', 
                text: 'Craft 16🌿 into 8🪢', 
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 16) {
                        inventory.palmLeaves -= 16;
                        inventory.rope = (inventory.rope || 0) + 8;
                        await inventory.save();
                        return { message: 'Rex crafts rope for you!\n**+8**🪢', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves!', color: '#ff0000' };
                    }
                }
            },
            { 
                emoji: '3️⃣', 
                text: 'Sell 30🪢 for 10✨', 
                result: async (interaction, inventory) => {
                    if (inventory.rope >= 30) {
                        inventory.rope -= 30;
                        inventory.gold = (inventory.rope || 0) + 10;
                        await inventory.save();
                        return { message: 'Rex gives you gold for your rope!\n**+10**✨', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves!', color: '#ff0000' };
                    }
                }
            },
            { 
                emoji: '4️⃣', 
                text: 'Ambush Rex', 
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
                    let embedColor = '#00ff00'; 
    
                    if (chance < 0.15) { // 15% chance you overpower Rex
                        inventory.gold = (inventory.gold || 0) + 5;
                        inventory.rope = (inventory.rope || 0) + 5;
                        await inventory.save();
                        resultMessage = '**You overpower Rex and defeat him!**\n**+5**✨ **+5**🪢';
                    } else if (chance < 0.75) { // 55% chance you and Rex have a scuffle
                        resultMessage = '**You and Rex have a scuffle, tossing your items around!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 1);
                                inventory[resource] -= amount;
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            }
                        });
                        await inventory.save();
                        embedColor = '#ffa500'; // Orange color for scuffle
                    } else { // 25% chance Rex overpowers you
                        resultMessage = '**Rex overpowers you and loots your resources!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 10);
                                inventory[resource] -= amount;
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            }
                        });
                        await inventory.save();
                        embedColor = '#ff0000'; // Red color for Rex overpowering
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            { 
                emoji: '5️⃣', 
                text: 'Leave', 
                result: () => ({ message: 'You decide to leave Rex and continue your exploration.', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274572311445635173/REXEVENT.png?ex=66c2bd77&is=66c16bf7&hm=51b48f281e43a17933bde33d083b48f70d8ea1dbe63c55d276a0ba0a0af0923e&'
    },
    {
        id: 5,
        description: "You meet Duko, an illegal rock dealer. 1 loot rock for **6**🪵 and **3**🪨",
        choices: [
            { emoji: '1️⃣', text: 'Leave', result: () => ({ message: 'You decide to leave Duko and continue your exploration.', color: '#0099ff' })},
            { emoji: '2️⃣', text: 'Buy 1 rock', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 1) },
            { emoji: '3️⃣', text: 'Buy 3 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 3) },
            { emoji: '4️⃣', text: 'Buy 5 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 5) },
            { emoji: '5️⃣', text: 'Buy 10 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 10) },
            { emoji: '6️⃣', text: 'Buy 20 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 20) },
            { emoji: '7️⃣', text: 'Buy 50 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 50) },
            { emoji: '8️⃣', text: 'Buy 100 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 100) },
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274616296985723056/DUKOEVENTROCKSD.png?ex=66c2e66e&is=66c194ee&hm=806de9a45039aef475a2eb79f82e05a62d7dedf1973aeff36c52a2d7527f71c0&'
    },
    {
        id: 6,
        description: "You encounter Triv, a feared swordsman, who challenges you to a 1v1 battle.",
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274674180419489822/1v1Triv.png?ex=66c31c56&is=66c1cad6&hm=566990eab2e9890a657e0f2c018f84c724f4a9776bd0ea3bb684af8f13b62df6&",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Flee',
                async result(interaction, inventory) {
                    const resources = ['wood', 'stone', 'copper'];
                    let resultMessage = "You flee from Triv, but you drop some resources in the process!\n";
                    
                    // Track resource losses
                    resources.forEach(resource => {
                        if (inventory[resource] > 0) {
                            inventory[resource] -= 1;
                            resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                        }
                    });
    
                    await inventory.save();
                    return { message: resultMessage, color: '#ff0000' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Fight with fists',
                async result(interaction, inventory) {
                    const outcome = Math.random();
                    let resultMessage = "";
                    let color;
    
                    if (outcome <= 0.40) {
                        resultMessage = "Triv destroys you in combat!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
    
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        color = '#ff0000';
                    } else if (outcome <= 0.60) {
                        resultMessage = "You and Triv exchange blows, resulting in a stalemate...";
                        color = '#ffff00';
                    } else {
                        resultMessage = "You disarm triv in battle and he flees, dropping resources!\n";
                        const resources = {
                            wood: [1, 3],
                            stone: [1, 3],
                            copper: [1, 3],
                            gold: [1, 3]
                        };
    
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        color = '#00ff00';
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Fight with your Axe (🪓 -10 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.metalAxe || tools.metalAxeDurability < 10) {
                        // User is defeated due to lack of durability
                        let resultMessage = "You fumble around and are swiftly defeated!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
                
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
                
                    // Deduct axe durability
                    tools.metalAxeDurability -= 10;
                    await tools.save();
                
                    let resultMessage = "Fight with your Axe (🪓 -10 Durability)\n";
                    const outcome = Math.random();
                    let color;
                
                    if (outcome <= 0.1) {
                        resultMessage += "Triv destroys you in combat!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
                
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        color = '#ff0000';
                    } else if (outcome <= 0.25) {
                        resultMessage += "You and Triv exchange blows, resulting in a stalemate...";
                        color = '#ffff00';
                    } else {
                        resultMessage += "You slay Triv in battle! You gain a wealth of resources.\n";
                        const resources = {
                            wood: [5, 15],
                            palmLeaves: [5, 15],
                            stone: [5, 15],
                            copper: [5, 15],
                            gold: [2, 12]
                        };
                
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        if (Math.random() <= 0.25) { // 25% small chance for ruby
                            inventory.ruby += 1;
                            resultMessage += `+1♦️ \n`;
                        }
                        color = '#00ff00';
                    }
                
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            }                  
        ]
    },
    {
        id: 7,
        description: "You encounter NF89, a blacksmith, who offers to craft tools or sell items.",
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274977215314133023/NFTHEBLACKSMITH.png?ex=66c43690&is=66c2e510&hm=8278fd5ea5fba7b55b544de5ab4a92043c1d68dd830ec432576f34a5510e3593&", // Use an appropriate image URL
        choices: [
            {
                emoji: '1️⃣',
                text: 'Craft Axe\n-30🪵 -60🪨 -60🔶 -20🪢 -15✨',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.wood < 30 || inventory.stone < 60 || inventory.copper < 60 || inventory.rope < 20 || inventory.gold < 15) {
                        let resultMessage = "You don’t have enough resources to craft an axe. NF89 shakes his head in disappointment.\n";
                        
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.wood -= 30;
                    inventory.stone -= 60;
                    inventory.copper -= 60;
                    inventory.rope -= 20;
                    inventory.gold -= 15;
    
                    // Check if user already has an axe and update durability or add a new one
                    if (tools.metalAxe) {
                        tools.metalAxeDurability = 50;
                    } else {
                        tools.metalAxe = true;
                        tools.metalAxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you a new axe 🪓!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Craft Pickaxe\n-30🪵 -60🪨 -60🔶 -20🪢 -15✨',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.wood < 30 || inventory.stone < 60 || inventory.copper < 60 || inventory.rope < 20 || inventory.gold < 15) {
                        let resultMessage = "You don’t have enough resources to craft a pickaxe. NF89 shakes his head in disappointment.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.wood -= 30;
                    inventory.stone -= 60;
                    inventory.copper -= 60;
                    inventory.rope -= 20;
                    inventory.gold -= 15;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.metalPickaxe) {
                        tools.metalPickaxeDurability = 50;
                    } else {
                        tools.metalPickaxe = true;
                        tools.metalPickaxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you a new pickaxe ⛏️!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Leave',
                async result() {
                    let resultMessage = "You decide to leave NF89’s workshop and continue on your journey.\n";
                    return { message: resultMessage, color: '#ffff00' };
                }
            }
        ]
    },
    {
        id: 8,
        description: "You encounter HHyper, an extra-large dragon who is in the middle of destroying H city. He offers to buy some of your goods though??",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Sell 100🪵 for 2♦️',
                result: async (interaction, inventory) => {
                    if (inventory.wood >= 100) {
                        inventory.wood -= 100;
                        inventory.ruby += 2;
                        await inventory.save();
                        return { message: 'You sell your wood!\n**+2**♦️', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough wood to trade!', color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '2️⃣',
                text: 'Sell 100🪨 for 2♦️',
                result: async (interaction, inventory) => {
                    if (inventory.stone >= 100) {
                        inventory.stone -= 100;
                        inventory.ruby += 2;
                        await inventory.save();
                        return { message: 'You sell your stone!\n**+2**♦️', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough stone to trade!', color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '3️⃣',
                text: 'Sell 100🌿 for 2♦️',
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 100) {
                        inventory.palmLeaves -= 100;
                        inventory.ruby += 2;
                        await inventory.save();
                        return { message: 'You sell your leaves!\n**+2**♦️', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves to trade!', color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '4️⃣',
                text: 'Sell 100 🔶 for 2 ♦️',
                result: async (interaction, inventory) => {
                    if (inventory.copper >= 100) {
                        inventory.copper -= 100;
                        inventory.ruby += 2;
                        await inventory.save();
                        return { message: 'You sell your copper!\n**+2**♦️', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough copper to trade!', color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '5️⃣',
                text: 'Ambush HHyper',
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    if (chance < 0.99){
                        let maxResource = 'wood';
                        let maxAmount = inventory.wood;
    
                        if (inventory.stone > maxAmount) {
                            maxResource = 'stone';
                            maxAmount = inventory.stone;
                        }
                        if (inventory.palmLeaves > maxAmount) {
                            maxResource = 'palmLeaves';
                            maxAmount = inventory.palmLeaves;
                        }
                        if (inventory.copper > maxAmount) {
                            maxResource = 'copper';
                            maxAmount = inventory.copper;
                        }
    
                        const amountLost = Math.min(30, maxAmount);
                        inventory[maxResource] -= amountLost;
                        await inventory.save();
    
                        return {
                            message: `HHyper is too big for you to fight, and you get obliterated! -${amountLost} ${maxResource === 'wood' ? '🪵' : maxResource === 'stone' ? '🪨' : maxResource === 'palmLeaves' ? '🌿' : '🔶'}`,
                            color: '#ff0000'
                        };
                    } else { // 5% chance to succeed
                        inventory.gold += 100;
                        await inventory.save();
                        return { message: 'Somehow you managed to defeat HHyper??\n**+100**✨', color: '#00ff00' };
                    }
                }
            },
            {
                emoji: '6️⃣',
                text: 'Leave',
                result: () => ({ message: 'You decide to leave HHyper alone and walk away.', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275748057174118400/HHYPER_1.png?ex=66c70477&is=66c5b2f7&hm=c774559b4beadb8ac6070ec43bf28601421434ec7f7c26b465f095d104711b45&'
    },
    {
        id: 9,
        description: "You meet Tbnr, a struggling shopkeeper. He looks at you funny before asking what you want to buy.",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Buy 100🪵 for 2♦️',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        inventory.wood += 100;
                        await inventory.save();
                        resultMessage = 'You buy tons of wood!\n**+100🪵**';
                    } else {
                        resultMessage = 'You don’t have enough rubies to buy 100 wood.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Buy 100🪨 for 2♦️',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        inventory.stone += 100;
                        await inventory.save();
                        resultMessage = 'You buy tons of stone!\n**+100🪨**';
                    } else {
                        resultMessage = 'You don’t have enough rubies.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Buy 100🍃 for 2♦️',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        inventory.palmLeaves += 100;
                        await inventory.save();
                        resultMessage = 'You buy tons of leaves!\n**+100🍃**';
                    } else {
                        resultMessage = 'You don’t have enough rubies.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Buy 100🔶 for 2♦️',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        inventory.copper += 100;
                        await inventory.save();
                        resultMessage = 'You buy tons of copper!\n**+100🔶**';
                    } else {
                        resultMessage = 'You don’t have enough rubies.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '5️⃣',
                text: 'Buy 10🪵 10🪨 10🍃 10🔶 for 10✨',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.gold >= 10) {
                        inventory.gold -= 10;
                        inventory.wood += 10;
                        inventory.stone += 10;
                        inventory.palmLeaves += 10;
                        inventory.copper += 10;
                        await inventory.save();
                        resultMessage = 'You buy a multitude of resources!\n**+10🪵 +10🪨 +10🍃 +10🔶**';
                    } else {
                        resultMessage = 'You don’t have enough gold.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '6️⃣',
                text: 'Buy 40🪢 for 30✨ 3♦️',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.gold >= 30 && inventory.ruby >= 3) {
                        inventory.rope += 40;
                        await inventory.save();
                        resultMessage = 'You buy tons of rope!\n**+40🪢**';
                    } else {
                        resultMessage = 'You don’t have enough gold or rubies.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '7️⃣',
                text: 'Leave',
                result: () => ({ message: 'You decide to leave the shopkeeper and continue your journey.', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275726750420303904/TBNRSHOP.png?ex=66c6f09f&is=66c59f1f&hm=6a5737a94c40cfada4b2feeeb47c2562e4e6c7aeec9903aad0cbb2b46e4f700f&'
    },    
    {
        id: 10,
        description: "Poor people... But I was once like them...\nAll of them, Josh, Rex, Tbnr, Dolphe...\nIf only we could activate the Negadom Destroyer...\n",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Craft Fishing Rod (-1💎 -10♦️ -40✨ -80🪵 -60🪢)',
                result: async (interaction, inventory, tools) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    // Check if the user has enough resources
                    if (inventory.diamond >= 1 && inventory.ruby >= 10 && inventory.gold >= 40 && inventory.wood >= 80 && inventory.rope >= 60) {
                        // Deduct resources
                        inventory.diamond -= 1;
                        inventory.ruby -= 10;
                        inventory.gold -= 40;
                        inventory.wood -= 80;
                        inventory.rope -= 60;
                        
                        // Set fishing rod with full durability
                        tools.fishingRod = 1;
                        tools.fishingRodDurability = 100;
                        
                        await tools.save();
                        await inventory.save();
                        resultMessage = 'JD helps you craft a fishing rod!\n**Fishing Rod crafted!** 🎣';
                    } else {
                        resultMessage = 'You do not have enough resources to craft the fishing rod.';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Leave',
                result: () => ({ message: 'You decide to leave JD and continue exploring.', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/935416283976048680/1275704210377412639/New_Piskel_2.png?ex=66c6dba1&is=66c58a21&hm=b9597c82245e578b102cbc907f3541a053c3f478d42d14d1ad3a5a1776f07578&'
    }
    
];
















//------------------------------------------------
// HELPER FGUNCTIONS
//------------------------------------------------
async function handleDolpheDonation(interaction, inventory, resource, emoji) {
    if (inventory[resource] >= 5) {
        inventory[resource] -= 5;
        const chance = Math.random();
        let resultMessage = '';

        if (chance < 0.8) {
            const resourceGained = 10;
            inventory[resource] += resourceGained;
            resultMessage = `Dolphe is actually MrBeast and gives you stuff in return!\n**+${resourceGained}** ${emoji}`;
        } else {
            resultMessage = `Dolphe graciously accepts your donation!\n**-5** ${emoji}.`;
            return { message: resultMessage, color: '#ffff00' }; // Green color for success
        }

        await inventory.save();
        return { message: resultMessage, color: '#00ff00' }; // Green color for success
    } else {
        return { message: `You don't have enough ${emoji} to donate!`, color: '#ff0000' }; // Red color for failure
    }
}
//------------------------------------------------
async function handleRockPurchase(interaction, inventory, quantity) {
    const woodCost = 6 * quantity;
    const stoneCost = 3 * quantity;

    if (inventory.wood < woodCost || inventory.stone < stoneCost) {
        return { message: `You don’t have enough resources to buy ${quantity} rock(s).`, color: '#ff0000' };
    }

    inventory.wood -= woodCost;
    inventory.stone -= stoneCost;
    await inventory.save();

    let resultMessage = `You bought ${quantity} rock(s) from Duko.\nOpening the rocks...\n`;
    for (let i = 0; i < quantity; i++) {
        const chance = Math.random() * 100;

        if (chance < 0.8) { // 0.8% chance to get 1💎
            inventory.diamond = (inventory.diamond || 0) + 1;
            resultMessage += '**《◊【༺LEGENDARY༻】◊》** You got 1 💎!\n';
        } else if (chance < 1.8) { // 1% chance to get 3-4♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 3;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《◊【༺LEGENDARY༻】◊》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 5.5) { // 3.7% chance to get 1-2♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 1;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《【EPIC】》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 10.0) { // 4.5% chance to get 4-7✨
            const goldAmount = Math.floor(Math.random() * 4) + 4;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**《【EPIC】》** You got ${goldAmount} ✨!\n`;
        } else if (chance < 19.0) { // 9% chance to get 1-3✨
            const goldAmount = Math.floor(Math.random() * 3) + 1;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**【RARE】** You got ${goldAmount} ✨!\n`;
        } else if (chance < 30.0) { // 11% chance to get 4-7🔶
            const copperAmount = Math.floor(Math.random() * 4) + 4;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**【RARE】** You got ${copperAmount} 🔶!\n`;
        } else if (chance < 45.0) { // 15% chance to get 2-3🔶
            const copperAmount = Math.floor(Math.random() * 2) + 2;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${copperAmount} 🔶!\n`;
        } else if (chance < 60.0) { // 15% chance to get 2-4🪨
            const stoneAmount = Math.floor(Math.random() * 3) + 2;
            inventory.stone = (inventory.stone || 0) + stoneAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${stoneAmount} 🪨!\n`;
        } else if (chance < 80.0) { // 20% chance to get 1🪨
            inventory.stone = (inventory.stone || 0) + 1;
            resultMessage += '**COMMON** You got 1 🪨!\n';
        } else if (chance < 100.0) { // 20% chance to get 1🔶
            inventory.copper = (inventory.copper || 0) + 1;
            resultMessage += '**COMMON** You got 1 🔶!\n';
        }
    }

    await inventory.save();
    return { message: resultMessage, color: '#00ff00' };
}














//------------------------------------------------
// THE COMMAND
//------------------------------------------------

const activeExplores = new Set();

module.exports = {
    data: new SlashCommandBuilder()
        .setName('explore')
        .setDescription('Explore and make choices to gain or lose resources.'),
    
        async execute(interaction) {
            const userId = interaction.user.id;
        
            // Check if the user is already exploring
            if (activeExplores.has(userId)) {
                return interaction.reply({
                    content: 'You are already exploring! Please wait until your current exploration is finished.',
                    ephemeral: true
                });
            }
        
            // Find or create the user, inventory, and tools
            const [user] = await User.findOrCreate({ where: { discordId: userId } });
            const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });
            const [tools] = await Tool.findOrCreate({ where: { userId: user.id } });
        
            // Cooldown check
            const now = Date.now();
            const cooldown = 20 * 1000; // 20 seconds
            const lastExplore = user.lastExplore || 0;
        
            if (now - lastExplore < cooldown) {
                const remainingTime = Math.ceil((cooldown - (now - lastExplore)) / 1000);
                return interaction.reply({ content: `Please wait ${remainingTime} seconds before exploring again.`, ephemeral: true });
            }
        
            // Add user to active explores set
            activeExplores.add(userId);
            
            try {
                // Update the lastExplore time
                user.lastExplore = now;
                await user.save();
        
                // Choose a random event
                const event = events[Math.floor(Math.random() * events.length)];

                // Create an embed for the event
                const embed = new EmbedBuilder()
                    .setColor('#0099ff')
                    .setTitle('Exploration Event!')
                    .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
                    .setDescription(event.description)
                    .setImage(event.imageUrl)
                    .addFields(event.choices.map(choice => ({ name: choice.emoji, value: choice.text, inline: true })))
                    .setFooter({ text: 'React with the number corresponding to your choice.' });
        
                // Send the embed and add reactions
                const message = await interaction.reply({ embeds: [embed], fetchReply: true });
                event.choices.forEach(choice => message.react(choice.emoji));
        
                // Set up a reaction collector
                const filter = (reaction, user) => event.choices.map(choice => choice.emoji).includes(reaction.emoji.name) && user.id === interaction.user.id;
                const collector = message.createReactionCollector({ filter, time: 60000 }); // 1 minute
        
                collector.on('collect', async (reaction) => {
                    const choice = event.choices.find(c => c.emoji === reaction.emoji.name);
                    // Ensure tools is defined and passed correctly
                    if (tools) {
                        const { message: resultMessage, color: embedColor } = await choice.result(interaction, inventory, tools);
        
                        const resultEmbed = new EmbedBuilder()
                            .setColor(embedColor)
                            .setTitle('Event Result')
                            .setDescription(resultMessage)
                            .setImage(event.imageUrl);
        
                        activeExplores.delete(userId);
        
                        await message.edit({ embeds: [resultEmbed] });
        
                        collector.stop();
                    } else {
                        console.error('Tools not found for user:', userId);
                    }
                });
        
                collector.on('end', (collected, reason) => {
                    if (reason === 'time') {
                        const timeoutEmbed = new EmbedBuilder()
                            .setColor('#ff0000')
                            .setTitle('Timeout')
                            .setDescription('You did not react in time. Please use the command again.')
                            .setImage(event.imageUrl);
        
                        message.edit({ embeds: [timeoutEmbed] });
        
                        activeExplores.delete(userId);
                    }
                });
        
            } 
            catch (error) 
            {
                console.error('Error executing explore command:', error);
                activeExplores.delete(userId);
                return interaction.reply({ content: 'An error occurred while executing the command. Please try again later.', ephemeral: true });
            } 
        } 
};