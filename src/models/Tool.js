const { Model, DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Adjust the path as needed

class Tool extends Model {}

Tool.init({
    userId: {
        type: DataTypes.INTEGER,
        allowNull: false,
        references: {
            model: 'Users', // Assumes your User model is named 'Users'
            key: 'id'
        },
        unique: true, // Ensures each user can only have one set of tools
    },
    metalAxe: {
        type: DataTypes.BOOLEAN,
        defaultValue: false,
        allowNull: false
    },
    metalAxeDurability: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        validate: {
            min: 0,
            max: 50
        }
    },
    metalPickaxe: {
        type: DataTypes.BOOLEAN,
        defaultValue: false,
        allowNull: false
    },
    metalPickaxeDurability: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        validate: {
            min: 0,
            max: 50
        }
    },
    fishingRod: {  // New fishing rod field
        type: DataTypes.BOOLEAN,
        defaultValue: false,
        allowNull: false
    },
    fishingRodDurability: {  // New fishing rod durability field
        type: DataTypes.INTEGER,
        defaultValue: 0,
        validate: {
            min: 0,
            max: 100
        }
    }
}, {
    sequelize,
    modelName: 'Tool',
    tableName: 'Tools',
    timestamps: false
});

module.exports = Tool;
