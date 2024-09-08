// models/AutoMachine.js
const { Model, DataTypes } = require('sequelize');
const sequelize = require('../dbConfig');

class AutoMachine extends Model {}

AutoMachine.init({
    userId: {
        type: DataTypes.INTEGER,
        allowNull: false,
    },
    type: {
        type: DataTypes.ENUM('autochopper', 'autominer', 'autoforager'),
        allowNull: false,
    },
    wood: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    rope: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    stone: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    copper: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    palmLeaves: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    berries: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    apples: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    upgradeLevel: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    lastCollected: {
        type: DataTypes.DATE,
        defaultValue: DataTypes.NOW,
    },
}, {
    sequelize,
    modelName: 'AutoMachine',
});

module.exports = AutoMachine;
