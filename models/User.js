const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Adjust if necessary

const User = sequelize.define('User', {
    discordId: {
        type: DataTypes.STRING,
        allowNull: false,
        unique: true,
    },
    wood: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        allowNull: false,
    },
    lastChop: {
        type: DataTypes.BIGINT, // Use BIGINT to store timestamp
        defaultValue: 0,
    },
});

module.exports = User;