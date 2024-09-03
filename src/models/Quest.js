const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig');

const Quest = sequelize.define('Quest', {
    userId: {
        type: DataTypes.INTEGER,
        allowNull: false,
        references: {
            model: 'Users', // Table name for User model
            key: 'id'
        },
    },
    questType: {
        type: DataTypes.STRING,
        allowNull: false,
    },
    isCompleted: {
        type: DataTypes.BOOLEAN,
        defaultValue: false,
    },
    progress: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    
    startTime: {
        type: DataTypes.DATE,
        allowNull: false,
    }
}, {
    timestamps: false,
});


module.exports = Quest;
