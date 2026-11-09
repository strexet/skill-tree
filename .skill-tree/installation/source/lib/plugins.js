'use strict';

// Acquisition and parameter resolution remain independent of activation and composition.
module.exports={...require('./plugin-sources.js'),...require('./plugin-parameters.js')};

// Management remains lazy so acquisition/parameter callers load no installation owner.
for(const name of ['inventory','formatInventory','prepareRemoval','applyRemoval','applyManagementChange','prepareUnbind','prepareActivation','forgetKnown','listMain'])module.exports[name]=(...args)=>require('./plugin-management.js')[name](...args);
