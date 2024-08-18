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
    gold: {
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
    rope: {   // New rope field
        type: DataTypes.INTEGER,
        defaultValue: 0
    },
});

module.exports = Inventory;
