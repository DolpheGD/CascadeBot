const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Ensure this path is correct

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
});

// Correct the association alias to match
User.hasOne(require('./Inventory'), { foreignKey: 'userId', as: 'inventory' });

module.exports = User;
