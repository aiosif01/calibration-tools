function y_hat = lm_func(t,a)
% y_hat = lm_func(t,a)
%  
% function for nonlinear least squares curve-fitting
% using the Levenberg-Marquardt function
%
% -------- INPUT VARIABLES ---------
%  t     = independent variable values (assumed to be error-free)        (m x 1)
%  a     = parameter values                                              (n x 1)
% 
% ---------- OUTPUT VARIABLES -------
% y_hat  = curve-fit fctn evaluated at points t and with parameters a    (m x 1)

copyfile('input~TEMPLATE.csv', 'input.csv');

csv = fileread('input.csv');
csv = strrep(csv, '__parameter_1__', num2str(single(a(1))));
csv = strrep(csv, '__parameter_2__', num2str(single(a(2))));
csv = strrep(csv, '__parameter_3__', num2str(single(a(3))));

fid = fopen('input.csv', 'w');
fwrite(fid, csv, '*char');
fclose(fid);

system('rm -rf results/');
system('make >out');
system('rm input.csv');

all_data = readtable('results/stats.csv');

y_hat = all_data{1:24:73, 3};
