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

    // general resources
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
    rope: {   // New rope field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    cloth: {   // New cloth field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },


    // forage resources
    berries: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    apples: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    watermelon: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    banana: { // NEW
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    coconut: { // NEW
        type: DataTypes.INTEGER,
        defaultValue: 0
    },



    // mine/ore resources
    copper: {  // New copper field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    gold: {   // Update gold field to use ✨
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    ruby: {    // New ruby field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    diamond: { // New diamond field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },



    // fish resources
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




    // mechanical resources
    negadomBattery: {  // New Negadom Destroyer battery field
        type: DataTypes.BOOLEAN,
        defaultValue: false
    },
    metalParts: {  // METAL PARTS
        type: DataTypes.INTEGER,
        defaultValue: 0
    }
});

module.exports = Inventory;
