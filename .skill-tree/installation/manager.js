#!/usr/bin/env node
'use strict';
const path=require('node:path');
const manager=require('./source/lib/installation.js');
process.exitCode=manager.localMain(path.resolve(__dirname,'../..'),path.join(__dirname,'source'),process.argv.slice(2));
