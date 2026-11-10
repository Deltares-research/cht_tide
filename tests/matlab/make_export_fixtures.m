% Golden files for cht_tide.export, made with the MATLAB Delft Dashboard writers.
% Run with: matlab -batch "run('make_export_fixtures.m')" from this folder.
ddb = 'c:\work\checkouts\git\oet_matlab\matlab-tools\applications\DelftDashBoard';

addpath(fullfile(ddb, 'general', 'fileio'));
out = fullfile(fileparts(mfilename('fullpath')), '..', 'data', 'export');
t = datenum(2020, 1, 1) + (0:5)/24;
wl = [1.2345 -0.5 0 12.25 -10.125 NaN];
exportTEK(wl', t', fullfile(out, 'point.tek'), '10.500_50.250');
