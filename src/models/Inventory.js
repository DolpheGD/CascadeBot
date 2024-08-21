const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Ensure this path is correct

const Inventory = sequelize.define('Inventory', {
    id: {
        type: DataTypes.INTEGER,
        autoIncrement: true,
        primaryKey: true
    },
    userId: {
        type: DataTypes.INTEGER,
        references: {
            model: 'Users', // Name of the Users table
            key: 'id'
        },
        allowNull: false
    },
    wood: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    stone: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    palmLeaves: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    gold: {   // Update gold field to use ✨
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    rope: {   // New rope field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    diamond: { // New diamond field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    ruby: {    // New ruby field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    copper: {  // New copper field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    fish: {    // New fish field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    rareFish: {  // New rare fish field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    superRareFish: {  // New super rare fish field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    legendaryFish: {  // New legendary fish field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    negadomBattery: {  // New Negadom Destroyer battery field
        type: DataTypes.BOOLEAN,
        defaultValue: false
    }
});

module.exports = Inventory;
