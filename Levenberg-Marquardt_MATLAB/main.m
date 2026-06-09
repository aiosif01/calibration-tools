%% 
clear all, close all, clc

hold off
randn('seed',0); % specify a particular random sequence for msmnt error

% number of simulation parameters to optimize
Npar = 3;
% lower & upper parameters boundaries
a_lb = [ 0.0000; 0.0100; 0.0100 ];
a_ub = [ 0.9999; 0.5000; 0.5000 ];
% initial guess parameters
a_init  = [ 0.0001; 0.1500; 0.2000 ];
% data to fit (i.e., cell population over time)
y_dat = [ 1118; 2544; 5997; 12089 ];
% independent variable (column vector) representing time
t = [0:24:72]';


% initial value of the measurement error
msmnt_err = 0.45;
% proper value of the weight is 1/(squared measurement error)
weight = 1 / msmnt_err^2;
% algorithmic parameters:
%      prnt MaxIter  eps1  eps2  eps3  eps4  lam0 lamUP lamDN UpdateType 
opts = [  3,  20000, 1e-3, 1e-3, 1e-2, 1e-2, 1e-1,  11,   9,         1 ];

% Levenberg-Marquardt
[a_fit,Chi_sq,sigma_a,sigma_y,corr,R_sq,cvg_hst] = ...
	lm('lm_func',a_init,t,y_dat,weight,-0.01,a_lb,a_ub,opts);
% output the result of the fit
y_fit = lm_func(t,a_fit);

disp('    initial   fit    sigma_a   percent')
disp(' -------------------------------------------------------')
disp ([ a_init, a_fit, sigma_a, 100*abs(sigma_a./a_fit) ])

n = length(a_fit);
Chi_sq, R_sq, corr

lm_plots(t,y_dat,y_fit,sigma_y,cvg_hst,'lm_example');
