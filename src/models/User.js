const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Ensure this path is correct
const Tool = require('./Tool');
const Quest = require('./Quest'); // Import the Quest model
const AutoMachine = require('./AutoMachine'); // Import the Quest model

const User = sequelize.define('User', {
    id: {
        type: DataTypes.INTEGER,
        autoIncrement: true,
        primaryKey: true
    },
    discordId: {
        type: DataTypes.STRING,
        unique: true,
        allowNull: false
    },
    username: {
        type: DataTypes.STRING,
        allowNull: false
    },
    lastChop: {
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
    lastMine: {
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
    
    lastExplore: {
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
    lastFish: {  // New lastFish field to track fishing cooldown
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
    lastForage: {  // New lastFish field to track fishing cooldown
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },

    lastDaily: {
        type: DataTypes.DATE, 
        allowNull: true,
    },
    // QUESTSSS
    lastQuest: { 
        type: DataTypes.BIGINT,
        defaultValue: 0,
    }
});

// Correct the association alias to match
User.hasOne(require('./Inventory'), { foreignKey: 'userId', as: 'inventory' });

User.hasOne(Tool, {
    foreignKey: 'userId',
    as: 'tools'
});

User.hasOne(Quest, { // Change this to hasOne
    foreignKey: 'userId',
    as: 'quest'
});

User.hasOne(AutoMachine, { // Change this to hasOne
    foreignKey: 'userId',
    as: 'automachine'
});

Tool.belongsTo(User, {
    foreignKey: 'userId'
});

Quest.belongsTo(User, {
    foreignKey: 'userId'
});

AutoMachine.belongsTo(User, {
    foreignKey: 'userId'
});

module.exports = User;
