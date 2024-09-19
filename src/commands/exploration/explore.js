const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool'); // Adjust the path as needed
const tools = require('../utility/tools');
const { trackQuestProgress } = require('../../commands/utility/quest.js');

const resourceEmojiMap = {
    wood: '🪵',
    stone: '🪨',
    palmLeaves: '🍃',
    copper: '🔶',
    rope: '🪢',
    gold: '✨',
    ruby: '♦️',
    diamond: '💎',
    berries: '🫐',
    apples: '🍎',
    watermelon: '🍉',
    cloth: '🧶'
};






//------------------------------------------------
// EVENTS
//------------------------------------------------
const events = [
    {
        id: 1,
        description: async (interaction, inventory, tools) => {
            let desc = "You spot Josh near a campfire";
            let randmessage = Math.random();

            // Add dynamic parts to the description based on the user's inventory or tools
            if (randmessage < 0.33 ) {
                desc += ". He doesn't notice you...";
            } else if (randmessage < 0.66) {
                desc += ". He seems to be crying about something...";
            } else {
                desc += ". He seems calm but you can't shake the feeling something's off.";
            }
            
            return desc;
        },
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
                            resultMessage = `Josh accepts your rubies and gives you a huge stack of wood!\n**+${woodGained}**🪵`;
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
                text: 'Give Josh fish -10🐟',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.fish >= 10) {
                        inventory.fish -= 10;
                        const chance = Math.random();
    
                        if (chance <= 0.7) { 
                            const goldgained = Math.floor(Math.random() * 3) + 1;
                            inventory.gold += goldgained;
                            resultMessage = `Josh cooks your fish and gives you gold!\n**+${goldgained}**✨`;
                        } else { 
                            const woodGained = Math.floor(Math.random() * 10) + 6;
                            inventory.wood += woodGained;
                            resultMessage = `Josh cooks your fish and gives you wood!\n**+${woodGained}**🪵`;
                        }
                    } else {
                        resultMessage = 'You don’t have enough fish!';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '5️⃣',
                text: 'Leave',
                result: () => ({ message: 'You run away!', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1275352717501665332/JOSHCAMPFIRE_1.png?ex=66c59446&is=66c442c6&hm=ab921b1d1c60330420fb37749ee9e02ecd2902672ea3cc5b4bdd230706dee121&'
    },
    {
        id: 2,
        description: async (interaction, inventory, tools) => {
            let desc = "You spot a homeless Dolphe";
            let randmessage = Math.random();

            // Add dynamic parts to the description based on the user's inventory or tools
            if (randmessage < 0.33 ) {
                desc += "and he is shivering from the cold...";
            } else if (randmessage < 0.66) {
                desc += ". He seems disguntled...";
            } else {
                desc += ". The Great Abyssnia Depression must have hit hard...";
            }
            
            return desc;
        },
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
        description: async (interaction, inventory, tools) => {
            let desc = "You come across Xender, a shady businessman. He has a prize pool of gold and diamonds.\n";
            let randmessage = Math.random();

            // Add dynamic parts to the description based on the user's inventory or tools
            if (randmessage < 0.33 ) {
                desc += "**Xender:** COME BIG WIN BIG WIN WIN 10✨ WIN 1💎";
            } else if (randmessage < 0.66) {
                desc += "**Xender:** I need FUNDING to launch attacks on HHyper. OUR NATION DEPENDS ON IT!!!";
            } else {
                desc += "**Xender:** THIS IS NOT A SCAM. WIN BIG 💎💎💎💎💎💎 WIN BIG";
            }
            
            return desc;
        },
        choices: [
            { emoji: '1️⃣', text: '[NOT SCAM Lottery] 1🪵 1🪨 1🌿 1🔶', result: async (interaction, inventory) => {
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
            { emoji: '2️⃣', text: '[SUPER NOT SCAM Lottery] 10✨', result: async (interaction, inventory) => {
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
        description: async (interaction, inventory, tools) => {
            let desc = "You meet Rex, an old crafter";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += ". He offers to craft your palm leaves into items.";
            } else if (randmessage < 0.50) {
                desc += ". He seems a bit beaten up for some reason...";
            } else if (randmessage < 0.75) {
                desc += " and it seems nobody is around his shop.";
            } else {
                desc += ". Weird how there is one random shop in the middle of the forest...";
            }
            
            return desc;
        },
        choices: [
            { 
                emoji: '1️⃣', 
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
                emoji: '2️⃣', 
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
                emoji: '3️⃣', 
                text: 'Craft 40🌿 4✨ into 10🧶', 
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 40 || inventory.gold > 4) {
                        inventory.palmLeaves -= 40;
                        inventory.gold -= 4;

                        inventory.cloth = (inventory.cloth || 0) + 4;

                        await inventory.save();
                        return { message: 'Rex crafts cloth for you!\n**+4**🧶', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves and gold!', color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '4️⃣',
                text: 'Craft Gloves -70🧶 -35✨ -10🪢',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.cloth < 70 || inventory.gold < 35 || inventory.rope < 10 ) {
                        let resultMessage = "You don’t have enough materials to craft gloves. Rex looks at you demonically.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.cloth -= 70;
                    inventory.gold -= 35;
                    inventory.rope -= 10;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.gloves) {
                        tools.glovesDurability = 100;
                    } else {
                        tools.gloves = true;
                        tools.glovesDurability = 100;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "You crafted gloves from Rex 🧤!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            { 
                emoji: '5️⃣', 
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
                emoji: '6️⃣', 
                text: 'Leave', 
                result: () => ({ message: 'You decide to leave Rex and continue your exploration.', color: '#0099ff' })
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274572311445635173/REXEVENT.png?ex=66c2bd77&is=66c16bf7&hm=51b48f281e43a17933bde33d083b48f70d8ea1dbe63c55d276a0ba0a0af0923e&'
    },
    {
        id: 5,
        description: async (interaction, inventory, tools) => {
            let desc = "You meet Duko, an illegal rock dealer. 1 loot rock for **6**🪵 and **3**🪨\n";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "**Duko:** Dont tell anyone about this...";
            } else if (randmessage < 0.50) {
                desc += "**Duko:** I may be illegal, but I'm telling you, Tbnr is way more fishy than me...";
            } else if (randmessage < 0.75) {
                desc += "He seems to be busy modeling something on his computer.";
            } else {
                desc += "He stares at you lifelessly.";
            }
            
            return desc;
        },
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
        description: async (interaction, inventory, tools) => {
            let desc = "";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "You encounter Triv, a feared assassin.";
            } else if (randmessage < 0.50) {
                desc += "**Triv:** You and I will fight to the death... FOR LOONAAAA!!";
            } else if (randmessage < 0.75) {
                desc += "**Triv:** I am always two steps ahead... People like you must be eliminated...";
            } else {
                desc += "You encounter Triv, who as been tasked by Xender to eliminate you.";
            }
            
            return desc;
        },
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
                text: 'Fight with your Axe (🪓 -5 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.metalAxe || tools.metalAxeDurability < 5) {
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
                    tools.metalAxeDurability -= 5;
                    await tools.save();
                
                    let resultMessage = "Fight with your Axe (🪓 -5 Durability)\n";
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
                    } else if (outcome <= 0.20) {
                        resultMessage += "You and Triv exchange blows, resulting in a stalemate...";
                        color = '#ffff00';
                    } else {
                        resultMessage += "You slay Triv in battle! You gain a wealth of resources.\n";
                        const resources = {
                            wood: [4, 11],
                            palmLeaves: [4, 11],
                            stone: [4, 11],
                            copper: [4, 11],
                            gold: [3, 7]
                        };
                
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        if (Math.random() <= 0.2) { // 20% small chance for ruby
                            inventory.ruby += 1;
                            resultMessage += `+1♦️ \n`;
                        }
                        color = '#00ff00';
                    }
                
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Fight with your Dagger (🗡️ -5 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.dagger || tools.daggerDurability < 5) {
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
                    tools.daggerDurability -= 5;
                    await tools.save();
                
                    let resultMessage = "Fight with your dagger (🗡️ -5 Durability)\n";
                
                        resultMessage += "You defeat Triv with the dagger! You gain a ton of resources.\n";
                        const resources = {
                            wood: [4, 11],
                            palmLeaves: [4, 11],
                            stone: [4, 11],
                            copper: [4, 11],
                            gold: [2, 6],
                            rope: [1, 4],
                            cloth: [1, 3]
                        }
                
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        if (Math.random() <= 0.4) { // 20% small chance for ruby
                            inventory.ruby += 1;
                            resultMessage += `+1♦️ \n`;
                        }
                        color = '#00ff00';
                
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274674180419489822/1v1Triv.png?ex=66c31c56&is=66c1cad6&hm=566990eab2e9890a657e0f2c018f84c724f4a9776bd0ea3bb684af8f13b62df6&"
    },
    {
        id: 7,
        description: async (interaction, inventory, tools) => {
            let desc = "";
            let randmessage = Math.random();

            if (randmessage < 0.4 ) {
                desc += "You encounter NF89, a blacksmith, who offers to forge tools.";
            } else if (randmessage < 0.8) {
                desc += "**NF89:** If you need anything forged, I'll get it done.";
            } else {
                desc += "**NF89:** Have you seen Ultra M anywhere? Ever since the highlands disaster he's been missing...";
            }
            
            return desc;
        },
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274977215314133023/NFTHEBLACKSMITH.png?ex=66c43690&is=66c2e510&hm=8278fd5ea5fba7b55b544de5ab4a92043c1d68dd830ec432576f34a5510e3593&",
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
                text: 'Craft Dagger\n-30🪵 -100🪨 -100🔶 -20🪢 -50✨ -10♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.wood < 30 || inventory.stone < 100 || inventory.copper < 100 || inventory.rope < 20 || inventory.gold < 50 || inventory.ruby < 10 ) {
                        let resultMessage = "You don’t have enough resources to craft a dagger. NF89 shakes his head in disappointment.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.wood -= 30;
                    inventory.stone -= 100;
                    inventory.copper -= 100;
                    inventory.rope -= 20;
                    inventory.gold -= 50;
                    inventory.ruby -= 10;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.dagger) {
                        tools.daggerDurability = 100;
                    } else {
                        tools.dagger = true;
                        tools.daggerDurability = 100;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you a new dagger 🗡️!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Craft 5⚙️\n -100🔶 -75🪨 -15✨ -2♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.stone < 75 || inventory.copper < 100 || inventory.gold < 15 || inventory.ruby < 2) {
                        let resultMessage = "You don’t have enough resources to metal parts.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.stone -= 75;
                    inventory.copper -= 100;
                    inventory.gold -= 15;
                    inventory.ruby -= 2;
                    // gain metal parts
                    inventory.metalParts += 5;
                
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you metal parts!\n**+5**⚙️";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '5️⃣',
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
        description: async (interaction, inventory, tools) => {
            let desc = "You encounter HHyper, an extra-large dragon who is in the middle of destroying H city.";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "\nYou can hear the cries of the people wanting art progress...";
            } else if (randmessage < 0.50) {
                desc += "\n**Hhyper:** RAWWRRRR XD";
            } else if (randmessage < 0.75) {
                desc += "\nA plane suddenly crashes into Hhyper's head.";
            } else {
                desc += "\nHHyper stops on a building, causing an earthquake.";
            }
            
            return desc;
        },
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
        description: async (interaction, inventory, tools) => {
            let desc = "You meet Tbnr, a struggling shopkeeper. ";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += " He looks at you seductively before asking what you want to buy.";
            } else if (randmessage < 0.50) {
                desc += " He turns around to check his \"Special Stock\".";
            } else if (randmessage < 0.75) {
                desc += " He seems to be doing something funny in the corner of the shop...";
            } else {
                desc += "\n**Tbnr:** Yes";
            }
            
            return desc;
        },
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
        description: async (interaction, inventory, tools) => {
            let desc = "You meet JD the fisherman.\n";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "**JD:** Poor people... But I was once like them... All of them, Josh, Rex, Tbnr, Dolphe... If only we could activate the Negadom Destroyer...";
            } else if (randmessage < 0.50) {
                desc += "**JD:** People keep fighting on the dock... Things haven't been the same since the Great Abyssnia Depression...";
            } else if (randmessage < 0.75) {
                desc += "**JD:** A certain duck keeps barging into my shop and eating all the fish... If you ever see him, please do me a favor...";
            } else {
                desc += "**JD:** Me and Josh used to be fishing buddies, but he got into gambling. I wonder where he is now...";
            }
            
            return desc;
        },
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
                text: 'Ambush JD',
                result: async (interaction, inventory) => {
                    const randomOutcome = Math.random();
                    let resultMessage = '';
                    let embedColor = '#ff0000'; // Default to red for failure
    
                    if (randomOutcome < 0.35) { // 35% chance to loot items
                        const berriesLoot = Math.floor(Math.random() * 6) + 1;
                        const fishLoot = Math.floor(Math.random() * 6) + 1;
                        const watermelonLoot = Math.random() < 0.7 ? Math.floor(Math.random() * 2) + 1: 0;
    
                        inventory.berries += berriesLoot;
                        inventory.fish += fishLoot;
                        inventory.watermelon += watermelonLoot;
                        await inventory.save();
                        
                        if (watermelonLoot > 0)
                            resultMessage = `You caught JD by surprise and looted his items!\n**+${berriesLoot}**🫐 **+${fishLoot}**🐟 **+${watermelonLoot}**🍉`;
                        else
                            resultMessage = `You caught JD by surprise and looted his items!\n**+${berriesLoot}**🫐 **+${fishLoot}**🐟`;
                        embedColor = '#00ff00'; // Green for success
    
                    } else if (randomOutcome < 0.65) { // 30% chance to fail due to Rohan and Josh
                        resultMessage = "Rohan and Josh are in the store too. I can't get away with ambushing JD now...";
                    } else { // 35% chance JD fights back
                        const goldLoss = Math.floor(Math.random() * 2) + 1;
    
                        inventory.gold = Math.max(0, inventory.gold - goldLoss);
                        await inventory.save();
    
                        resultMessage = `JD is prepared and knocks you out!\n**-${goldLoss}** ✨`;
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Leave',
                result: () => ({ message: 'You decide to leave JD and continue exploring.', color: '#0099ff' }) // Blue for neutral
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/935416283976048680/1275704210377412639/New_Piskel_2.png?ex=66c6dba1&is=66c58a21&hm=b9597c82245e578b102cbc907f3541a053c3f478d42d14d1ad3a5a1776f07578&'
    },    
    {
        id: 11,
        description:  async (interaction, inventory, tools) => {
            let desc = "You meet Rohan the fruit vendor.\n";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "**Rohan:** If you ever see Josh around, don't talk to him. He can't be trusted...";
            } else if (randmessage < 0.50) {
                desc += "**Rohan:** Since the Great Abyssnia Depression, I've had to sell fruit. I used to have Daddy's and Mommy's money but they wont give me any now...";
            } else if (randmessage < 0.75) {
                desc += "**Rohan:** Everyone is oblivious to my divine powers... *He* will get what is coming to him...";
            } else {
                desc += "**Rohan:** I can't stand that Rex guy. He's always supportive of Josh...";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Sell 40🫐 for 4✨',
                result: async (interaction, inventory) => {
                    if (inventory.berries >= 40) {
                        inventory.berries -= 40;
                        inventory.gold += 4;
                        await inventory.save();
                        return { message: 'You sold berries to Rohan!\n**+5**✨', color: '#00ff00' }; // Green for success
                    } else {
                        return { message: 'You do not have enough berries.', color: '#ff0000' }; // Red for failure
                    }
                }
            },
            {
                emoji: '2️⃣',
                text: 'Sell 20🍎 for 4✨',
                result: async (interaction, inventory) => {
                    if (inventory.apples >= 20) {
                        inventory.apples -= 20;
                        inventory.gold += 4;
                        await inventory.save();
                        return { message: 'You sold apples to Rohan!\n**+5**✨', color: '#00ff00' }; // Green for success
                    } else {
                        return { message: 'You do not have enough apples.', color: '#ff0000' }; // Red for failure
                    }
                }
            },
            {
                emoji: '3️⃣',
                text: 'Sell 10🍉 for 1♦️',
                result: async (interaction, inventory) => {
                    if (inventory.watermelon >= 10) {
                        inventory.watermelon -= 10;
                        inventory.ruby += 1;
                        await inventory.save();
                        return { message: 'You sold watermelon to Rohan!\n**+1**♦️', color: '#00ff00' }; // Green for success
                    } else {
                        return { message: 'You do not have enough watermelon.', color: '#ff0000' }; // Red for failure
                    }
                }
            },
            {
                emoji: '4️⃣',
                text: 'Ambush Rohan [🗡️?]',
                result: async (interaction, inventory, tools) => {
                    const durabilityUsed = Math.floor(Math.random() * 7) + 1;
                    const randgold = Math.floor(Math.random() * 6) + 10;

                    if (tools.dagger && tools.daggerDurability > durabilityUsed) {
                        tools.metalPickaxeDurability -= durabilityUsed;
                        
                        await tools.save();

                        inventory.gold += randgold;
                        return { message: `(🗡️ -${durabilityUsed} Durability)\nYou ambushed Rohan with your dagger! He flees and you gained gold!\n**+${randgold}✨**`, color: '#00ff00' }; // Green for success
                    }


                    if (Math.random() < 0.7) { // 70% chance of failure
                        // Determine the most abundant resource
                        const resources = [
                            { type: 'wood', amount: inventory.wood },
                            { type: 'stone', amount: inventory.stone },
                            { type: 'copper', amount: inventory.copper },
                            { type: 'palmLeaves', amount: inventory.palmLeaves },
                            { type: 'berries', amount: inventory.berries },
                            { type: 'apples', amount: inventory.apples }
                        ];
                        const mostAbundantResource = resources.reduce((max, resource) => resource.amount > max.amount ? resource : max, resources[0]);
                        
                        // Deduct resources
                        const lossAmount = Math.min(10, mostAbundantResource.amount);
                        inventory[mostAbundantResource.type] -= lossAmount;
                        await inventory.save();
                        
                        return { message: `You tried to ambush Rohan, but he used his divine powers to destroy you!\n**-${lossAmount}** ${mostAbundantResource.type === 'wood' ? '🪵' : mostAbundantResource.type === 'stone' ? '🪨' : mostAbundantResource.type === 'copper' ? '🔶' : mostAbundantResource.type === 'palmLeaves' ? '🌿' : mostAbundantResource.type === 'berries' ? '🫐' : '🍎'}`, color: '#ff0000' }; // Red for failure
                    } else {
                        inventory.gold += 3
                        return { message: 'You managed to ambush Rohan successfully! He flees and you gained some gold.\n**+1✨**', color: '#00ff00' }; // Green for success
                    }
                }
            },
            {
                emoji: '5️⃣',
                text: 'Leave',
                result: () => ({ message: 'You decide to leave Rohan and continue exploring.', color: '#0099ff' }) // Blue for neutral
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/935416283976048680/1277522580164575284/ROHANfruitvendor.png?ex=66cd791e&is=66cc279e&hm=579a404fdb45f84946d0f0f214bdc0c3ed16f6be0eef1551c2f95bc0ac7cb078&'
    },
    {
        id: 12,
        description: async (interaction, inventory, tools) => {
            let desc = "You encounter Daffysamlake who spots a cave in the distance.\n";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += "**Daffysamlake:** Lets go explore the cave together!";
            } else if (randmessage < 0.50) {
                desc += "**Daffysamlake:** If we go together, we have a better chance of surviving...";
            } else if (randmessage < 0.75) {
                desc += "**Daffysamlake:** STARMASTER TO THE RESCUE!!!! *Runs off into the cave*";
            } else {
                desc += "Daffysamlake looks down at his near-broken pickaxe and grins...";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Explore the cave with Daffysamlake',
                async result(interaction, inventory) {
                    let resultMessage = "You explore the cave with Daffysamlake and gain resources!\n";
    
                    // Guaranteed resources
                    const stoneGain = Math.floor(Math.random() * 5) + 1; // 1-5 stone
                    const copperGain = Math.floor(Math.random() * 3) + 1; // 1-3 copper
                    inventory.stone += stoneGain;
                    inventory.copper += copperGain;
                    resultMessage += `+${stoneGain} 🪨\n+${copperGain} 🔶\n`;
    
                    // 75% chance for wood
                    if (Math.random() <= 0.75) {
                        const woodGain = Math.floor(Math.random() * 4) + 1; // 1-4 wood
                        inventory.wood += woodGain;
                        resultMessage += `+${woodGain} 🪵\n`;
                    }
    
                    // 75% chance for berries
                    if (Math.random() <= 0.75) {
                        const berriesGain = Math.floor(Math.random() * 3) + 1; // 1-3 berries
                        inventory.berries += berriesGain;
                        resultMessage += `+${berriesGain} 🫐\n`;
                    }
    
                    // 20% chance for rope
                    if (Math.random() <= 0.20) {
                        const ropeGain = Math.floor(Math.random() * 2) + 1; // 1-2 rope
                        inventory.rope += ropeGain;
                        resultMessage += `+${ropeGain} 🪢\n`;
                    }
    
                    // 20% chance for palm leaves
                    if (Math.random() <= 0.20) {
                        const palmLeavesGain = Math.floor(Math.random() * 3) + 1; // 1-3 palm leaves
                        inventory.palmLeaves += palmLeavesGain;
                        resultMessage += `+${palmLeavesGain} 🍃\n`;
                    }
    
                    // 10% chance for gold
                    if (Math.random() <= 0.10) {
                        inventory.gold += 1;
                        resultMessage += `+1 ✨\n`;
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Explore the cave by yourself (⛏️ -5 durability)',
                async result(interaction, inventory, tools) {
                    let resultMessage = "";
                    const outcome = Math.random();
    
                    // Deduct 5 durability from the pickaxe if the user has one
                    if (tools.metalPickaxe) {
                        tools.metalPickaxeDurability -= 5;
                        await tools.save();
                    }
    
                    if (outcome <= 0.9) { // 90% chance for a positive result
                        resultMessage = "You explore the cave on your own and gain a multitude of resources!\n";
    
                        // Guaranteed resources
                        const stoneGain = Math.floor(Math.random() * 15) + 3; 
                        const copperGain = Math.floor(Math.random() * 8) + 3; 
                        const woodGain = Math.floor(Math.random() * 8) + 3; 
                        inventory.stone += stoneGain;
                        inventory.copper += copperGain;
                        inventory.wood += woodGain;
                        resultMessage += `+${stoneGain} 🪨\n+${copperGain} 🔶\n+${woodGain} 🪵\n`;
    
                        // 80% chance for berries
                        if (Math.random() <= 0.80) {
                            const berriesGain = Math.floor(Math.random() * 5) + 1; // 1-5 berries
                            inventory.berries += berriesGain;
                            resultMessage += `+${berriesGain} 🫐\n`;
                        }
    
                        // 75% chance for rope
                        if (Math.random() <= 0.75) {
                            const ropeGain = Math.floor(Math.random() * 5) + 1; // 1-5 rope
                            inventory.rope += ropeGain;
                            resultMessage += `+${ropeGain} 🪢\n`;
                        }
    
                        // 75% chance for palm leaves
                        if (Math.random() <= 0.75) {
                            const palmLeavesGain = Math.floor(Math.random() * 4) + 1; // 1-4 palm leaves
                            inventory.palmLeaves += palmLeavesGain;
                            resultMessage += `+${palmLeavesGain} 🍃\n`;
                        }
    
                        // 90% chance for gold
                        if (Math.random() <= 0.90) {
                            const goldGain = Math.floor(Math.random() * 4) + 1; // 1-4 gold
                            inventory.gold += goldGain;
                            resultMessage += `+${goldGain} ✨\n`;
                        }
    
                        // 10% chance for ruby
                        if (Math.random() <= 0.1) {
                            inventory.ruby += 1;
                            resultMessage += `+1 ♦️\n`;
                        }
    
                        // 20% chance for metal parts
                        if (Math.random() <= 0.2) {
                            inventory.metalParts += 1;
                            resultMessage += `+1⚙️\n`;
                        }
    
                        await inventory.save();
                        return { message: resultMessage, color: '#00ff00' };
                    } else { // 15% chance for a negative result
                        resultMessage = "You explore the cave but Daffysamlake got all of it first!\n";
                        
                        // Minimal resources
                        const stoneGain = Math.floor(Math.random() * 2) + 1; // 1-2 stone
                        const woodGain = Math.floor(Math.random() * 2) + 1; // 1-2 wood
                        inventory.stone += stoneGain;
                        inventory.wood += woodGain;
                        resultMessage += `+${stoneGain} 🪨\n+${woodGain} 🪵\n`;
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/1135808718492139521/1280078811680997448/Daffysamlake.png?ex=66d6c5cb&is=66d5744b&hm=146e266445515a61fd8feae066021d157ab9e77a960e77baf45162fbcc0128c9&"
    },
    {
        id: 13,
        description: async (interaction, inventory, tools) => {
            let desc = "You stumble upon thedoggyp's abandoned shack.";
            let randmessage = Math.random();

            if (randmessage < 0.25 ) {
                desc += " There is no life to be seen for miles...";
            } else if (randmessage < 0.50) {
                desc += " There is a faint but putrid odor coming from the shack.";
            } else if (randmessage < 0.75) {
                desc += " Looks like he fell victim to gambling...";
            } else {
                desc += " You swear you heard something moving inside.";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Loot the house',
                async result(interaction, inventory) {
                    const outcome = Math.random();
                    let resultMessage = "";
    
                    if (outcome <= 0.85) {
                        resultMessage = "You find some loot in the shack!\n";
                        const resources = {
                            wood: [1, 6],
                            stone: [1, 6],
                            rope: [0, 2]
                        };
    
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            if (gained > 0) {  // Only add to message if resource > 0
                                inventory[resource] += gained;
                                resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                            }
                        }
    
                    } else {
                        resultMessage = "Turns out thedoggyp is still in his shack! He attacks you!\n";
                        const losses = {
                            stone: 1,
                            palmLeaves: 1,
                            berries: 1
                        };
    
                        for (const [resource, loss] of Object.entries(losses)) {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= loss;
                                resultMessage += `-${loss} ${resourceEmojiMap[resource]}\n`;
                            }
                        }
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: outcome <= 0.85 ? '#00ff00' : '#ff0000' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Deconstruct the house (🪓 -5 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.metalAxe || tools.metalAxeDurability < 5) {
                        // No axe or not enough durability
                        return {
                            message: "You don't have a sturdy enough axe to deconstruct the house!",
                            color: '#ff0000'
                        };
                    }
    
                    // Deduct axe durability
                    tools.metalAxeDurability -= 5;
                    await tools.save();
    
                    // Gain materials from deconstructing the house
                    let resultMessage = "You deconstruct the house and gather materials!\n";
                    const resources = {
                        wood: [10, 40],
                        stone: [5, 20],
                        rope: [2, 8]
                    };
    
                    for (const [resource, range] of Object.entries(resources)) {
                        const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                        inventory[resource] += gained;
                        resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                    }
    
                    // Bonus loot if thedoggyp was in the house
                    if (Math.random() <= 0.30) {
                        resultMessage += "Turns out thedoggyp was in his shack! He runs away in terror, dropping some loot!\n";
                        const bonusLoot = {
                            gold: [1, 2],
                            copper: [2, 5]
                        };
    
                        for (const [resource, range] of Object.entries(bonusLoot)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Forage outside the house',
                async result(interaction, inventory) {
                    // Gather fruit around the house
                    let resultMessage = "You find some fruit around the house!\n";
                    const resources = {
                        berries: [1, 4],
                        apples: [1, 4]
                    };
    
                    for (const [resource, range] of Object.entries(resources)) {
                        const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                        inventory[resource] += gained;
                        resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: '#00ff00' };
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/1135808718492139521/1280078811379011604/FrancisShack.png?ex=66d6c5cb&is=66d5744b&hm=0345e04f90f924040942f2a99fda32cb4c181ab0c12dc1aa12c51a2275371286&"
    },
    {
        id: 14,
        description: async (interaction, inventory, tools) => {
            let desc = "You, Tbnr, and Josh paint a picture of Hu Tao from Genshin Impact.\n";
            let randmessage = Math.random();

            if (randmessage < 0.17 ) {
                desc += "**Tbnr:** UWooooohghaa😳😳😳";
            } else if (randmessage < 0.34) {
                desc += "Josh looks like he just saw a murder...";
            } else if (randmessage < 0.51) {
                desc += "**Josh:** The painting... it are amazing...";
            } else if (randmessage < 0.68) {
                desc += "Tbnr gets unusually close to the painting.";
            } else if (randmessage < 0.85) {
                desc += "Josh looks desperate to sell the painting and immediately gamble afterwards.";
            } else {
                desc += "**Tbnr:** 🤤🤤🤤🤤🤤🤤🤤";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Sell the painting',
                async result(interaction, inventory) {
                    const buyers = ['Dolphe', 'thedoggyp', 'Rex', 'Bioniq', 'caliper', 'Rohan'];
                    const randomBuyer = buyers[Math.floor(Math.random() * buyers.length)];
                    const goldEarned = Math.floor(Math.random() * 2) + 1;
                    
                    inventory.gold += goldEarned;
                    await inventory.save();
    
                    const resultMessage = `You sold the painting to ${randomBuyer} and split the profits!\n+${goldEarned} ✨`;
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Backstab Tbnr and Josh',
                async result(interaction, inventory) {
                    const outcome = Math.random();
                    let resultMessage = "";
    
                    if (outcome <= 0.50) {
                        const goldEarned = Math.floor(Math.random() * 4) + 2;
                        inventory.gold += goldEarned;
                        resultMessage = `You backstab Tbnr and Josh and sell the painting yourself!\n+${goldEarned} ✨`;
                    } else {
                        const losses = {
                            gold: 1,
                            wood: 3,
                            stone: 3,
                            copper: 3
                        };
                        resultMessage = "You attempt to backstab Tbnr and Josh, but they destroy you in the process!\n";
                        
                        for (const [resource, loss] of Object.entries(losses)) {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= loss;
                                resultMessage += `-${loss} ${resourceEmojiMap[resource]}\n`;
                            }
                        }
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: outcome <= 0.50 ? '#00ff00' : '#ff0000' };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Destroy the painting! (🪓 -2 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.metalAxe || tools.metalAxeDurability < 2) {
                        // No axe or not enough durability
                        return {
                            message: "You don't have a sturdy enough axe to destroy the painting!",
                            color: '#ff0000'
                        };
                    }
    
                    // Deduct axe durability
                    tools.metalAxeDurability -= 2;
                    await tools.save();
    
                    // Gain rewards for destroying the painting
                    let resultMessage = "You destroy the painting! NF89 gives you a reward for being based!\n";
                    const resources = {
                        gold: [2, 8],
                        copper: [2, 12]
                    };
    
                    for (const [resource, range] of Object.entries(resources)) {
                        const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                        inventory[resource] += gained;
                        resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                    }
    
                    // 5% chance to get a ruby
                    if (Math.random() <= 0.05) {
                        inventory.ruby += 1;
                        resultMessage += `+1♦️`;
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: '#00ff00' };
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/1135808718492139521/1280090730525884479/hutao_tbnr_UPDATE.png?ex=66d6d0e5&is=66d57f65&hm=fc3807ed503c57ff78d77f2b541fd6dfd7f4d3ddc745db984a6262e5b6ecc721&"
    },
    {
        id: 15,
        description:  async (interaction, inventory, tools) => {
            let desc = "You stumble across a chest while wandering in a dense jungle.\n";
            let randmessage = Math.random();

            if (randmessage < 0.2 ) {
                desc += "The chest reeks of a salty odor. Maybe Tbnr was here before...";
            } else if (randmessage < 0.4) {
                desc += "You can see Rex watching at you from a distance...";
            } else if (randmessage < 0.6) {
                desc += "Maybe the chest is booby trapped?";
            } else if (randmessage < 0.8) {
                desc += "You remember Josh told you about this chest yesterday. Is it real?";
            } else {
                desc += "You can hear the singing of animals in the Jungle.";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Open the chest',
                async result(interaction, inventory) {
                    // Define possible resource gains
                    const resources = [
                        { name: 'wood', min: 1, max: 4, emoji: '🪵' },
                        { name: 'stone', min: 1, max: 4, emoji: '🪨' },
                        { name: 'copper', min: 1, max: 4, emoji: '🔶' },
                        { name: 'palmLeaves', min: 1, max: 4, emoji: '🍃' },
                        { name: 'berries', min: 1, max: 4, emoji: '🫐' },
                        { name: 'apples', min: 1, max: 3, emoji: '🍎' },
                        { name: 'rope', min: 1, max: 2, emoji: '🪢' },
                        { name: 'gold', min: 1, max: 2, emoji: '✨' },
                        { name: 'fish', min: 1, max: 4, emoji: '🐟' },
                        { name: 'rareFish', min: 1, max: 2, emoji: '🐠' },
                        { name: 'superRareFish', min: 1, max: 1, emoji: '🐡' }
                    ];
    
                    // Randomly select 4 resources to give
                    const selectedResources = [];
                    while (selectedResources.length < 4) {
                        const randomResource = resources[Math.floor(Math.random() * resources.length)];
                        if (!selectedResources.includes(randomResource)) {
                            selectedResources.push(randomResource);
                        }
                    }
    
                    // Prepare a message and update the user's inventory
                    let resultMessage = "You open the chest and find:\n";
                    for (const resource of selectedResources) {
                        const gainedAmount = Math.floor(Math.random() * (resource.max - resource.min + 1)) + resource.min;
                        inventory[resource.name] += gainedAmount;
                        resultMessage += `+${gainedAmount} ${resource.emoji}\n`;
                    }
    
                    // Save the inventory
                    await inventory.save();
    
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Leave',
                async result() {
                    return { message: "You leave the chest untouched and continue your journey.", color: '#ffcc00' };
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/935416283976048680/1282258289005953064/Chest.png?ex=66deb397&is=66dd6217&hm=f1a9b3e9ea31234cede1d8f6ea765a7f8cd6787957b58c7bb56b3918bf0f29cd&"
    },
    {
        id: 16,
        description: async (interaction, inventory, tools) => {
            let desc = "You stumble across a shiny-looking chest while exploring the Void Plains.\n";
            let randmessage = Math.random();

            if (randmessage < 0.2 ) {
                desc += "The chest reeks of a salty odor. Tbnr was definitely here before...";
            } else if (randmessage < 0.4) {
                desc += "You can hear laser weapons go off in the distance.";
            } else if (randmessage < 0.6) {
                desc += "You can hear an argument in the background between Josh and Rohan. Hopefully it doesn't escalate.";
            } else if (randmessage < 0.8) {
                desc += "While looking at the chest, an explosion goes off next to you.";
            } else {
                desc += "You can hear a faint buzzing from the void matter.";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Open the chest',
                async result(interaction, inventory) {
                    const outcome = Math.random();
    
                    if (outcome <= 0.90) {
                        // 90% chance: User gains random resources
                        const resources = [
                            { name: 'wood', min: 2, max: 8, emoji: '🪵' },
                            { name: 'stone', min: 2, max: 8, emoji: '🪨' },
                            { name: 'copper', min: 2, max: 8, emoji: '🔶' },
                            { name: 'palmLeaves', min: 2, max: 8, emoji: '🍃' },
                            { name: 'berries', min: 2, max: 8, emoji: '🫐' },
                            { name: 'apples', min: 2, max: 6, emoji: '🍎' },
                            { name: 'rope', min: 2, max: 4, emoji: '🪢' },
                            { name: 'gold', min: 2, max: 4, emoji: '✨' },
                            { name: 'fish', min: 2, max: 8, emoji: '🐟' },
                            { name: 'rareFish', min: 2, max: 4, emoji: '🐠' },
                            { name: 'superRareFish', min: 1, max: 2, emoji: '🐡' },
                            { name: 'legendaryFish', min: 1, max: 1, emoji: '🦈' },
                            { name: 'ruby', min: 1, max: 1, emoji: '♦️' }, 
                            { name: 'metalParts', min: 1, max: 1, emoji: '⚙️' }
                        ];
    
                        // Randomly select 3 resources to give
                        const selectedResources = [];
                        while (selectedResources.length < 3) {
                            const randomResource = resources[Math.floor(Math.random() * resources.length)];
                            if (!selectedResources.includes(randomResource)) {
                                selectedResources.push(randomResource);
                            }
                        }
    
                        // Prepare a message and update the user's inventory
                        let resultMessage = "You open the chest and find:\n";
                        for (const resource of selectedResources) {
                            const gainedAmount = Math.floor(Math.random() * (resource.max - resource.min + 1)) + resource.min;
                            inventory[resource.name] += gainedAmount;
                            resultMessage += `+${gainedAmount} ${resource.emoji}\n`;
                        }
    
                        // Save the inventory
                        await inventory.save();
    
                        return { message: resultMessage, color: '#00ff00' };
                    } else {
                        // 10% chance: Josh steals everything
                        const missedResources = [];
    
                        for (let i = 0; i < 3; i++) {
                            const randomResource = resources[Math.floor(Math.random() * resources.length)];
                            const missedAmount = Math.floor(Math.random() * (randomResource.max - randomResource.min + 1)) + randomResource.min;
                            missedResources.push(`-${missedAmount} ${randomResource.emoji}`);
                        }
    
                        const resultMessage = `Josh saw you opening the chest and stole the items!\nYou missed out on:\n${missedResources.join('\n')}`;
    
                        return { message: resultMessage, color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '2️⃣',
                text: 'Leave',
                async result() {
                    return { message: "You leave the shiny chest untouched and continue your journey.", color: '#ffcc00' };
                }
            }
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/935416283976048680/1282262478696349746/Upgrade_chest.png?ex=66deb77e&is=66dd65fe&hm=b3edfb649c1488c1b1147b06aa56e85645354de20894a81edd83f490fc9bc835&"
    },
    {
        id: 17,
        description: async (interaction, inventory, tools) => {
            let desc = "While wandering the barren wastelands of Glacier 15, you meet Frost, a fish vendor.\n";
            let randmessage = Math.random();

            if (randmessage < 0.2 ) {
                desc += "**Frost:** Last week I got fired from Xender Corp. I used to be a Janitor...";
            } else if (randmessage < 0.4) {
                desc += "He has clear muscle definition on his arms.";
            } else if (randmessage < 0.6) {
                desc += "**Frost:** The Great Abyssnia Depression is destroying the job market... I can't go on like this...";
            } else if (randmessage < 0.8) {
                desc += "Frost nervously looks over his shoulder, as Josh treks along the Glacier.";
            } else {
                desc += "The frigid air sticks to your skin.";
            }
            
            return desc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Sell 50🐟 for 15✨',
                async result(interaction, inventory) {
                    if (inventory.fish >= 50) {
                        inventory.fish -= 50;
                        inventory.gold += 15;
                        await inventory.save();
                        return { message: "You traded 50🐟 for 15✨.", color: '#00ff00' };
                    } else {
                        return { message: "You don't have enough fish to make this trade.", color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '2️⃣',
                text: 'Sell 25🐠 for 20✨',
                async result(interaction, inventory) {
                    if (inventory.rareFish >= 25) {
                        inventory.rareFish -= 25;
                        inventory.gold += 20;
                        await inventory.save();
                        return { message: "You traded 25🐠 for 20✨.", color: '#00ff00' };
                    } else {
                        return { message: "You don't have enough rare fish to make this trade.", color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '3️⃣',
                text: 'Sell 15🐡for 2♦️',
                async result(interaction, inventory) {
                    if (inventory.superRareFish >= 15) {
                        inventory.superRareFish -= 15;
                        inventory.ruby += 2;
                        await inventory.save();
                        return { message: "You traded 15🐡 for 2♦️.", color: '#00ff00' };
                    } else {
                        return { message: "You don't have enough super rare fish to make this trade.", color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '4️⃣',
                text: 'Trade 5🦈 for 1♦️',
                async result(interaction, inventory) {
                    if (inventory.legendaryFish >= 5) {
                        inventory.legendaryFish -= 5;
                        inventory.ruby += 1;
                        await inventory.save();
                        return { message: "You traded 5🦈 for 1♦️.", color: '#00ff00' };
                    } else {
                        return { message: "You don't have enough legendary fish to make this trade.", color: '#ff0000' };
                    }
                }
            },
            {
                emoji: '5️⃣',
                text: 'Ambush Frost',
                async result(interaction, inventory) {
                    const outcome = Math.random();
                    let resultMessage = "";
    
                    if (outcome <= 0.35) {
                        // 35% chance: User beats Frost
                        const fishLost = Math.floor(Math.random() * 26);
                        inventory.fish -= fishLost;
                        resultMessage = `You manage to beat Frost to a pulp!\n+${fishLost} 🐟`;
                    } else if (outcome <= 0.65) {
                        // 30% chance: Exchange blows
                        const fishLost = Math.min(inventory.fish, Math.floor(Math.random() * 5) + 1);
                        inventory.fish -= fishLost;
                        resultMessage = `You and Frost exchange blows with fish flying everywhere...\n-${fishLost} 🐟`;
                    } else {
                        // 35% chance: Frost defeats the user
                        const resourcesLost = {
                            wood: 10,
                            stone: 10,
                            palmLeaves: 10,
                            copper: 10
                        };
    
                        for (const [resource, loss] of Object.entries(resourcesLost)) {
                            if (inventory[resource] > 0) {
                                const actualLoss = Math.min(inventory[resource], loss);
                                inventory[resource] -= actualLoss;
                                resultMessage += `-${actualLoss} ${resourceEmojiMap[resource]}\n`;
                            }
                        }
    
                        resultMessage = "Frost JANITOR punches you and you instantly evaporate!\n" + resultMessage;
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: outcome <= 0.35 ? '#00ff00' : (outcome <= 0.65 ? '#ffcc00' : '#ff0000') };
                }
            },
            {
                emoji: '6️⃣',
                text: 'Leave',
                async result() {
                    return { message: "You leave Frost's fish stand and continue on your way.", color: '#ffcc00' };
                }
            },
        ],
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1282278127363559547/jani_1.png?ex=66dec611&is=66dd7491&hm=a6b23eca0bcb8ade3c9be2c4296c63f9d692b2d58a196a16f27a76f961fc357d&"
    },
    {
        id: 18,
        description: async (interaction, inventory, tools) => {
            let fulldesc = "After hitting it big, Josh personally invites you to a game of Blackjack.\n";
            let randmessage = Math.random();

            if (randmessage < 0.2 ) {
                fulldesc += "**Josh:** Your move...";
            } else if (randmessage < 0.4) {
                fulldesc += "Josh fastens his tie and looks up from his cards, grinning.";
            } else if (randmessage < 0.6) {
                fulldesc += "**Josh:** ... ";
            } else if (randmessage < 0.8) {
                fulldesc += "**Josh:** The haters... look at me now... im hit it big... ";
            } else {
                fulldesc += "Josh gives an intimidating aura...";
            }
              
            // Draw initial cards for the user and dealer
            const userCards = drawCards(2);
            const dealerCards = drawCards(2);
    
            // Save the drawn cards in interaction to access later
            interaction.userCards = userCards;
            interaction.dealerCards = dealerCards;
    
            // Format the cards for the description
            const userCardsStr = userCards.join(' ');
            const dealerCardsStr = '? ' + dealerCards[0];
    
            // Prepare the description
            fulldesc += `\n\nYour cards: ${userCardsStr}\nJosh's cards: ${dealerCardsStr}`;
            return fulldesc;
        },
        choices: [
            {
                emoji: '1️⃣',
                text: 'Stand',
                result: async (interaction, inventory) => {
                    return await handleStand(interaction, inventory);
                }
            },
            {
                emoji: '2️⃣',
                text: 'Hit',
                result: async (interaction, inventory) => {
                    let userCards = interaction.userCards || [];

                    // Draw a new card for the user
                    const newCard = drawCards(1)[0];
                    userCards.push(newCard);
    
                    // Update the interaction with the new hand
                    interaction.userCards = userCards;
    
                    // Continue the game with the updated hand
                    return await handleStand(interaction, inventory);
                }
            },
            {
                emoji: '3️⃣',
                text: 'Hit twice',
                result: async (interaction, inventory) => {
                    let userCards = interaction.userCards || [];

                    // Draw a new card for the user
                    const newCard = drawCards(1)[0];
                    const newCard2 = drawCards(1)[0];
                    userCards.push(newCard);
                    userCards.push(newCard2);
    
                    // Update the interaction with the new hand
                    interaction.userCards = userCards;
    
                    // Continue the game with the updated hand
                    return await handleStand(interaction, inventory);
                }
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/1274821354591621232/1282558991163199539/Joshjack.png?ex=66dfcba4&is=66de7a24&hm=c01b108d9a28105b761708f2f9358456ce668dd4963c791735b21da3a5448fbf&'
    },
    {
        id: 19,
        description: async (interaction, inventory, tools) => {
            let desc = "You meet Broskm, an illegal fruit dealer. 1 fruit case for **1**✨\n";
            let randMessage = Math.random();
    
            if (randMessage < 0.25) {
                desc += "**Broskm:** Keep this under wraps, yeah?";
            } else if (randMessage < 0.50) {
                desc += "**Broskm:** I ain't like Duko, trust me, my stuff's fresher.";
            } else if (randMessage < 0.75) {
                desc += "Broskm is inspecting his inventory with a grin.";
            } else {
                desc += "He gives you a sly wink.";
            }
    
            return desc;
        },
        choices: [
            { emoji: '1️⃣', text: 'Leave', result: () => ({ message: 'You decide to leave Broskm and continue your exploration.', color: '#0099ff' }) },
            { emoji: '2️⃣', text: 'Buy 1 fruit case', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 1) },
            { emoji: '3️⃣', text: 'Buy 3 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 3) },
            { emoji: '4️⃣', text: 'Buy 5 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 5) },
            { emoji: '5️⃣', text: 'Buy 10 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 10) },
            { emoji: '6️⃣', text: 'Buy 20 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 20) },
            { emoji: '7️⃣', text: 'Buy 50 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 50) },
            { emoji: '8️⃣', text: 'Buy 100 fruit cases', result: async (interaction, inventory) => await handleFruitPurchase(interaction, inventory, 100) },
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/1135808718492139521/1285513578308304969/Broskm_the_fruit_dealer.png?ex=66ea8b50&is=66e939d0&hm=ce3d2aa7d96bde3bd87a8ae41c924cc6e42509a24799fa3c318e7046e36d3c3b&'
    },
    {
        id: 20,
        description: async (interaction, inventory, tools) => {
            let desc = "You encounter Boss John, who runs a flower shop.";
            let randmessage = Math.random();

            if (randmessage < 0.2 ) {
                desc += "Boss John gives you a big smile.";
            } else if (randmessage < 0.4) {
                desc += "**Boss John:** No matter who COME to my STORE, I make SURE do everything I can to HELP.";
            } else if (randmessage < 0.6) {
                desc += "**Boss John:** If you need SUPPLIES, I GOT YOU!";
            } else if (randmessage < 0.8) {
                desc += "Boss John stands outside, greeting everyone who walks by.";
            } else {
                desc += "**Boss John:** Have you SEE Ultra M? I have not see him... AM WORRY...";
            }
            
            return desc;
        },
        imageUrl: "https://cdn.discordapp.com/attachments/1135808718492139521/1286202437346000896/BOSSJOHN.png?ex=66ed0cdd&is=66ebbb5d&hm=7a9c6715e6745c06247721448223c901598a6d54f8b69f844b5468eaaa1af736&",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Buy an Axe -10♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.ruby < 10) {
                        let resultMessage = "You don’t have enough rubies to buy an axe. Boss John says theres gonna be a discount later.\n";
                        
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.ruby -= 10;
    
                    // Check if user already has an axe and update durability or add a new one
                    if (tools.metalAxe) {
                        tools.metalAxeDurability = 50;
                    } else {
                        tools.metalAxe = true;
                        tools.metalAxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "You bought an axe from Boss John 🪓!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Buy a Pickaxe -10♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.ruby < 10) {
                        let resultMessage = "You don’t have enough rubies to buy a pickaxe. Boss John says theres gonna be a discount later.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.ruby -= 10;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.metalPickaxe) {
                        tools.metalPickaxeDurability = 50;
                    } else {
                        tools.metalPickaxe = true;
                        tools.metalPickaxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "You bought a pickaxe from Boss John ⛏️!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Buy Gloves -15♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.ruby < 15) {
                        let resultMessage = "You don’t have enough rubies to buy gloves. Boss John says theres gonna be a discount later.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.ruby -= 15;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.gloves) {
                        tools.glovesDurability = 100;
                    } else {
                        tools.gloves = true;
                        tools.glovesDurability = 100;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "You bought gloves from Boss John 🧤!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Buy 5⚙️ -10♦️',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.ruby < 10) {
                        let resultMessage = "You don’t have enough rubies to buy metal parts.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.ruby -= 10;

                    // gain metal parts
                    inventory.metalParts += 5;
                
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you metal parts!\n**+5**⚙️";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '5️⃣',
                text: 'Leave',
                async result() {
                    let randwood = Math.floor(Math.random() * 5 + 2);
                    let resultMessage = `You decide to leave boss John's and continue on your journey.\nYou pick up a couple logs on your way home!\n**+${randwood}**🪵`;
                    return { message: resultMessage, color: '#ffff00' };
                }
            }
        ]
    },
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
// DUKO ROCk
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

        if (chance < 1) { // 1% chance to get 1💎
            inventory.diamond = (inventory.diamond || 0) + 1;
            resultMessage += '**《◊【༺LEGENDARY༻】◊》** You got 1 💎!\n';
        } else if (chance < 2) { // 1% chance to get 3-4♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 3;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《◊【༺LEGENDARY༻】◊》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 6) { // 4% chance to get 1-2♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 1;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《【EPIC】》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 10.0) { // 4% chance to get 4-7✨
            const goldAmount = Math.floor(Math.random() * 4) + 4;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**《【EPIC】》** You got ${goldAmount} ✨!\n`;
        } else if (chance < 20.0) { // 10% chance to get 1-3✨
            const goldAmount = Math.floor(Math.random() * 3) + 1;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**【RARE】** You got ${goldAmount} ✨!\n`;
        } else if (chance < 30.0) { // 10% chance to get 4-7🔶
            const copperAmount = Math.floor(Math.random() * 4) + 4;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**【RARE】** You got ${copperAmount} 🔶!\n`;
        }
        // UNCOMMONS
        else if (chance < 40.0) { // 10% chance to get 2-3🔶
            const copperAmount = Math.floor(Math.random() * 2) + 2;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${copperAmount} 🔶!\n`;
        } else if (chance < 50.0) { // 10% chance to get 2-5 wood
            const woodAmount = Math.floor(Math.random() * 4) + 2;
            inventory.wood = (inventory.wood || 0) + woodAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${woodAmount} 🪵!\n`;
        } else if (chance < 60.0) { // 10% chance to get 2-4 stone
            const stoneAmount = Math.floor(Math.random() * 3) + 2;
            inventory.stone = (inventory.stone || 0) + stoneAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${stoneAmount} 🪨!\n`;
        }
        // COMMONS
        else if (chance < 75.0) { // 15% chance to get 1🪨
            inventory.stone = (inventory.stone || 0) + 1;
            resultMessage += '**COMMON** You got 1 🪨!\n';
        } 
        else if (chance < 85.0) { // 10% chance to get 1🔶
            inventory.copper = (inventory.copper || 0) + 1;
            resultMessage += '**COMMON** You got 1 🔶!\n';
        }
        else if (chance < 100.0) { // 15% chance to get 1🔶
            inventory.wood = (inventory.wood || 0) + 1;
            resultMessage += '**COMMON** You got 1 🪵!\n';
        }
    }

    await inventory.save();
    return { message: resultMessage, color: '#00ff00' };
}
//------------------------------------------------
// BROSKM FRUIT
//------------------------------------------------
async function handleFruitPurchase(interaction, inventory, quantity) {
    const goldCost = 1 * quantity;

    if (inventory.gold < goldCost) {
        return { message: `You don’t have enough gold to buy ${quantity} fruit case(s).`, color: '#ff0000' };
    }

    inventory.gold -= goldCost;
    await inventory.save();

    let resultMessage = `You bought ${quantity} fruit case(s) from Broskm.\nOpening the cases...\n`;
    for (let i = 0; i < quantity; i++) {
        const chance = Math.random() * 100;

        // LEGENDARY
        if (chance < 0.5) { // 0.5% chance to get 1 🥥
            inventory.coconut = (inventory.coconut || 0) + 1;
            resultMessage += '**《◊【༺LEGENDARY༻】◊》** You got 1 🥥!\n';
        } 
        // EPIC
        else if (chance < 2.5) { // 2.5% chance to get 1-3 🍌
            const bananaAmount = Math.floor(Math.random() * 3) + 1;
            inventory.banana = (inventory.banana || 0) + bananaAmount;
            resultMessage += `**《【EPIC】》** You got ${bananaAmount} 🍌!\n`;
        } else if (chance < 4.5) { // 2% chance to get 1-3 metalParts
            const metalPartsAmount = Math.floor(Math.random() * 3) + 1;
            inventory.metalParts = (inventory.metalParts || 0) + metalPartsAmount;
            resultMessage += `**《【EPIC】》** You got ${metalPartsAmount} ⚙️!\n`;
        } 
        // RARE
        else if (chance < 9.5) { // 5% chance to get 1-3 watermelon
            const watermelonAmount = Math.floor(Math.random() * 3) + 1;
            inventory.watermelon = (inventory.watermelon || 0) + watermelonAmount;
            resultMessage += `**【RARE】** You got ${watermelonAmount} 🍉!\n`;
        } else if (chance < 14.5) { // 5% chance to get 1-3 gold
            const goldAmount = Math.floor(Math.random() * 3) + 1;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**【RARE】** You got ${goldAmount} ✨!\n`;
        } else if (chance < 19.5) { // 5% chance to get 4-7 🍎
            const appleAmount = Math.floor(Math.random() * 4) + 4;
            inventory.apple = (inventory.apple || 0) + appleAmount;
            resultMessage += `**【RARE】** You got ${appleAmount} 🍎!\n`;
        } 
        // UNCOMMON
        else if (chance < 29.5) { // 10% chance to get 1-4 🍎
            const appleAmount = Math.floor(Math.random() * 4) + 1;
            inventory.apple = (inventory.apple || 0) + appleAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${appleAmount} 🍎!\n`;
        } else if (chance < 39.5) { // 10% chance to get 1-4 🪢
            const ropeAmount = Math.floor(Math.random() * 4) + 1;
            inventory.rope = (inventory.rope || 0) + ropeAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${ropeAmount} 🪢!\n`;
        } else if (chance < 49.5) { // 10% chance to get 1-4 🧶
            const clothAmount = Math.floor(Math.random() * 4) + 1;
            inventory.cloth = (inventory.cloth || 0) + clothAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${clothAmount} 🧶!\n`;
        } 
        // COMMON
        else if (chance < 64.5) { // 15% chance to get 1-4 🪵
            const woodAmount = Math.floor(Math.random() * 4) + 1;
            inventory.wood = (inventory.wood || 0) + woodAmount;
            resultMessage += `**COMMON** You got ${woodAmount} 🪵!\n`;
        } else if (chance < 79.5) { // 15% chance to get 1-4 🍃
            const leafAmount = Math.floor(Math.random() * 4) + 1;
            inventory.leaf = (inventory.leaf || 0) + leafAmount;
            resultMessage += `**COMMON** You got ${leafAmount} 🍃!\n`;
        } else if (chance < 99.5) { // 20% chance to get 1-4 berries
            const berryAmount = Math.floor(Math.random() * 4) + 1;
            inventory.berries = (inventory.berries || 0) + berryAmount;
            resultMessage += `**COMMON** You got ${berryAmount} 🫐!\n`;
        }
    }

    await inventory.save();
    return { message: resultMessage, color: '#00ff00' };
}
//------------------------------------------------
// Utility functions FOR BLACKJACK
//------------------------------------------------
function drawCards(num) {
    const suits = ['♠️', '♣️', '♦️', '♥️'];
    const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    const deck = [];

    for (const suit of suits) {
        for (const value of values) {
            deck.push(`${value}${suit}`);
        }
    }

    // Shuffle deck
    for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
    }

    return deck.splice(0, num);
}

function calculateHandValue(cards) {
    const cardValueMap = {
        'J': 10,
        'Q': 10,
        'K': 10,
        'A': 11
    };

    let total = 0;
    let aceCount = 0;

    for (const card of cards) {
        // Use regular expression to extract the card value
        const value = card.match(/^\d+|[JQKA]/)[0];
        
        if (cardValueMap.hasOwnProperty(value)) {
            total += cardValueMap[value];
            if (value === 'A') aceCount++;
        } else {
            total += parseInt(value, 10); // Convert numeric cards to integers
        }
    }

    // Adjust for aces if necessary
    while (total > 21 && aceCount > 0) {
        total -= 10; // Convert ace from 11 to 1
        aceCount--;
    }

    return total;
}

async function dealerTurn(dealerCards) {
    let dealerValue = calculateHandValue(dealerCards);

    while (dealerValue < 17) {
        dealerCards.push(...drawCards(1)); // Draw one card
        dealerValue = calculateHandValue(dealerCards);
    }

    return dealerCards;
}

// Function to handle the Stand logic
async function handleStand(interaction, inventory) {
    const userCards = interaction.userCards || [];
    const dealerCards = interaction.dealerCards || [];

    // Dealer's turn
    const finalDealerCards = await dealerTurn(dealerCards);

    // Calculate the final values
    const userValue = calculateHandValue(userCards);
    const dealerValue = calculateHandValue(finalDealerCards);

    // Determine the outcome
    let outcomeMessage = '';
    if (userValue > 21) {
        outcomeMessage = 'You bust! You lose! Looks like another easy victory for Josh!\n-5🪵\n-5🪨\n-5🌿\n-5🔶';
        await adjustResourcesOnLoss(inventory);
    }
    else if (dealerValue > 21) {
        const goldIncrease = Math.floor(Math.random() * 3) + 4; // +4 to +6 gold
        inventory.gold += goldIncrease;
        outcomeMessage = `Josh busts! You win! Poor Josh is going to lose his job now...\n${goldIncrease}✨`;
    }
    else if (userValue > dealerValue) {
        const goldIncrease = Math.floor(Math.random() * 3) + 4; // +4 to +6 gold
        inventory.gold += goldIncrease;
        outcomeMessage = `You win! Looks like Josh has to pay out the rest of his fortune...\n+${goldIncrease}✨`;
    }
    else if (userValue < dealerValue) {
        outcomeMessage = 'You lose! Josh laughs and tells you to play more!\n-5🪵\n-5🪨\n-5🌿\n-5🔶';
        await adjustResourcesOnLoss(inventory);
    }
    else {
        outcomeMessage = 'It\'s a tie!';
    }

    // Format the final hands
    const userCardsStr = userCards.join(' ');
    const finalDealerCardsStr = finalDealerCards.join(' ');

    // Prepare the result message
    const resultMessage = `Your hand: ${userCardsStr} (Value: ${userValue})\nJosh's hand: ${finalDealerCardsStr} (Value: ${dealerValue})\n\n${outcomeMessage}`;

    await inventory.save();

    return { message: resultMessage, color: outcomeMessage.includes('win') ? '#00ff00' : '#ff0000' };
}

// Function to adjust resources on loss
async function adjustResourcesOnLoss(inventory) {
    const resources = ['wood', 'stone', 'palmLeaves', 'copper'];
    const adjustment = { wood: -5, stone: -5, palmLeaves: -5, copper: -5 };

    for (const resource of resources) {
        if (inventory[resource] > 0) {
            const deduction = Math.min(inventory[resource], 5);
            inventory[resource] -= deduction;
            if (deduction > 0) {
                await inventory.save();
            }
        }
    }
}
//------------------------------------------------















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
            await interaction.deferReply();
            
            // Check if the user is already exploring
            if (activeExplores.has(userId)) {
                return interaction.editReply({
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
            const cooldown = 10 * 1000; // 14 seconds
            const lastExplore = user.lastExplore || 0;
        
            if (now - lastExplore < cooldown) {
                const remainingTime = Math.ceil((cooldown - (now - lastExplore)) / 1000);
                return interaction.editReply({ content: `Please wait ${remainingTime} seconds before exploring again.`, ephemeral: true });
            }
        
            // Add user to active explores set
            activeExplores.add(userId);
            
            try {
                // Update the lastExplore time
                user.lastExplore = now;
                await user.save();
        
                // Choose a random event
                const event = events[Math.floor(Math.random() * events.length)];

                // Generate dynamic description
                let eventDescription;
                if (typeof event.description === 'function') {
                    eventDescription = await event.description(interaction, inventory, tools);
                } else {
                    eventDescription = event.description;
                }

                // Create an embed for the event
                const embed = new EmbedBuilder()
                    .setColor('#0099ff')
                    .setTitle('Exploration Event!')
                    .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
                    .setDescription(eventDescription)
                    .setImage(event.imageUrl)
                    .addFields(event.choices.map(choice => ({ name: choice.emoji, value: choice.text, inline: true })))
                    .setFooter({ text: 'React with the number corresponding to your choice.' });
        
                // Send the embed and add reactions
                const message = await interaction.editReply({content: '', embeds: [embed], fetchReply: true });
                event.choices.forEach(choice => message.react(choice.emoji));
        
                // Set up a reaction collector
                const filter = (reaction, user) => event.choices.map(choice => choice.emoji).includes(reaction.emoji.name) && user.id === interaction.user.id;
                const collector = message.createReactionCollector({ filter, time: 70000 }); // 1 minute
        
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
        
                        await message.edit({content: '', embeds: [resultEmbed] });

                        // Success exploring -> progress updates
                        const questResult = await trackQuestProgress(interaction.user.id, 'explore', interaction); 
                        
                        if (questResult != 'No active quest found.') {
                            const questEmbed = new EmbedBuilder()
                                .setTitle('Quest Update')
                                .setDescription(questResult)
                                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                                .setColor('#00ff00');
                            return interaction.followUp({content: '', embeds: [questEmbed] });
                        }

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
        
                        message.edit({content: '', embeds: [timeoutEmbed] });
        
                        activeExplores.delete(userId);
                    }
                });
        
            } 
            catch (error) 
            {
                console.error('Error executing explore command:', error);
                activeExplores.delete(userId);
                return interaction.editReply({ content: 'An error occurred while executing the command. Please try again later.', ephemeral: true });
            } 
        } 
};