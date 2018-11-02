## Processing networks and optimizing yield strengths for all 200 new Greenland networks
## 18 Oct 2018 - EHU

from netCDF4 import Dataset
import numpy as np
import matplotlib.pyplot as plt
import csv
import collections
#from matplotlib.colors import LogNorm
from matplotlib import cm
#from shapely.geometry import *
from scipy import interpolate
from scipy.ndimage import gaussian_filter
from plastic_utilities_v2 import *
from GL_model_tools import *
from flowline_class_hierarchy import *

##-------------------
### READING IN BED
### COMMENT OUT IF DATA IS ALREADY READ IN TO YOUR SESSION
##-------------------

print 'Reading in surface topography'
gl_bed_path ='Documents/1. Research/2. Flowline networks/Model/Data/BedMachine-Greenland/BedMachineGreenland-2017-09-20.nc'
fh = Dataset(gl_bed_path, mode='r')
xx = fh.variables['x'][:].copy() #x-coord (polar stereo (70, 45))
yy = fh.variables['y'][:].copy() #y-coord
s_raw = fh.variables['surface'][:].copy() #surface elevation
h_raw=fh.variables['thickness'][:].copy() # Gridded thickness
b_raw = fh.variables['bed'][:].copy() # bed topo
thick_mask = fh.variables['mask'][:].copy()
ss = np.ma.masked_where(thick_mask !=2, s_raw)#mask values: 0=ocean, 1=ice-free land, 2=grounded ice, 3=floating ice, 4=non-Greenland land
hh = np.ma.masked_where(thick_mask !=2, h_raw) 
#bb = np.ma.masked_where(thick_mask !=2, b_raw)
bb = b_raw #don't mask, to allow bed sampling from modern bathymetry (was subglacial in ~2006)
## Down-sampling
X = xx[::2]
Y = yy[::2]
S = ss[::2, ::2]
H = hh[::2, ::2] 
B = bb[::2, ::2]
M = thick_mask[::2,::2]
## Not down-sampling
#X = xx
#Y = yy
#S = ss
fh.close()

#Smoothing bed to check effect on dLdt
unsmoothB = B
smoothB = gaussian_filter(B, 2)
#B_processed = np.ma.masked_where(thick_mask !=2, smoothB)

#Replacing interpolated surface with bed+thickness
S_new = np.add(B, H)

S_interp = interpolate.RectBivariateSpline(X, Y[::-1], S_new.T[::, ::-1])
H_interp = interpolate.RectBivariateSpline(X, Y[::-1], H.T[::, ::-1])
B_interp = interpolate.RectBivariateSpline(X, Y[::-1], smoothB.T[::, ::-1])
def NearestMaskVal(x0,y0):
    x_idx = np.abs(X-x0).argmin()
    y_idx = np.abs(Y-y0).argmin()
    return M[y_idx, x_idx]


##-------------------
### READ IN AND PROCESS ONE NETWORK AT A TIME
##-------------------

glacier_ids = range(1,195) #tell the function which MEaSUREs glacier IDs you want to process.
not_present = (93, 94, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 159, 161, 169, 172, 173, 177) #glacier IDs missing from set
for n in not_present:
    try:
        glacier_ids.remove(n)
    except ValueError:
        pass
#glacier_ids = range(1,10) #abbreviated test set

beds_foranalysis = []
termheights_foranalysis = []
optimal_taus = []
optimal_yieldtypes = []

base_fpath = 'Documents/1. Research/2. Flowline networks/Auto_selected-networks/Gld-autonetwork-GID'

secondary_gids = range(153,195)
for n in not_present:
    try:
        secondary_gids.remove(n)
    except ValueError:
        pass
for gid in secondary_gids:
    print 'Reading in glacier ID: '+str(gid)
    if gid<160:
        filename = base_fpath+str(gid)+'-date_2018-10-03.csv'
    else:
        filename = base_fpath+str(gid)+'-date_2018-10-04.csv' #workaround because I ran these in batches and saved them with the date
    
    coords_list = Flowline_CSV(filename, has_width=True, flip_order=False)
    nlines = len(coords_list)
    branch_0 = Branch(coords=coords_list[0], index=0, order=0) #saving central branch as main
    branch_list = [branch_0]
    if nlines>0:
        for l in range(1, nlines):
            branch_l = Branch(coords = coords_list[l], index=l, order=1, flows_to=0)
            branch_list.append(branch_l)
        nw = PlasticNetwork(name='GID'+str(gid), init_type='Branch', branches=branch_list, main_terminus=branch_0.coords[0])
        nw.make_full_lines()
    
    print 'Now processing glacier ID: '+str(gid)
    nw.process_full_lines(B_interp, S_interp, H_interp)
    nw.remove_floating()
    nw.make_full_lines()
    nw.process_full_lines(B_interp, S_interp, H_interp)
    
    print 'Now finding BedMachine terminus and optimizing glacier ID: '+str(gid)
    idx, term_bm = next((i,c) for i,c in enumerate(nw.flowlines[0].coords) if NearestMaskVal(c[0], c[1])==2) #need to do error handling in case this is nowhere satisfied
    print 'BedMachine terminus is at index {}, coords {}'.format(idx, term_bm)
    #idx, term_bm = next((i, c) for i, c in enumerate(nw.flowlines[0].coords) if S_interp(c[0], c[1])>2.0) #testing with surface cutoff (2m) for now instead of retrieving mask
    term_arcval = ArcArray(nw.flowlines[0].coords)[idx]
    term_bed = nw.flowlines[0].bed_function(term_arcval)
    term_surface = nw.flowlines[0].surface_function(term_arcval)
    print 'Surface elevation at this terminus is {}. Bed elevation is {}.'.format(term_surface, term_bed)
    beds_foranalysis.append(term_bed)
    termheights_foranalysis.append(term_surface)
    try:
        nw.optimize_network_yield(check_all=False, testrange=arange(0e3, 500e3, 5e3), nw_initial_termpos=term_arcval, use_balancethick=False, allow_upstream_breakage=False)
        optimal_taus.append(nw.flowlines[0].optimal_tau)
        optimal_yieldtypes.append(nw.network_yield_type)
        print 'Optimal yield strength for GID {} is {}, {}'.format(gid, nw.flowlines[0].optimal_tau, nw.network_yield_type)
    except UnboundLocalError: #type of error returned when no optimal value is found
        print 'Error finding optimal yield strength for glacier ID {}'.format(gid)
        optimal_taus.append(np.nan)
        optimal_yieldtypes.append('error')
        
#    
    #for fln in nw.flowlines:
    #    fln.yield_type = nw.network_yield_type
    #    fln.optimal_tau = nw.network_tau #actually I think this has already been done in optimize_network_yield...but we'll leave it for now
    #nw.network_ref_profiles()
    
out_dir = 'Documents/1. Research/2. Flowline networks/Auto_selected-networks/Optimization_analysis/'
output_fn = out_dir + 'bestfit_taus-fromdate_{}.csv'.format(datetime.date.today())
with open(output_fn, 'wb') as csvfile:
    linewriter = csv.writer(csvfile, delimiter=',')
    linewriter.writerow(['Glacier ID', 'Optimal yield strength [Pa]', 'Yield type', 'Terminal bed [m a.s.l.]', 'Terminal SE [m a.s.l.]'])
    for n, gid in enumerate(glacier_ids):
        linewriter.writerow([gid, optimal_taus[n], optimal_yieldtypes[n], beds_foranalysis[n], termheights_foranalysis[n]])
