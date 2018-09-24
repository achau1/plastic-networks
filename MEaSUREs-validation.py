## Loading in MEaSUREs terminus position data for Greenland to assess utility for validating hindcasts
## 12 Sept 2018  EHU

from netCDF4 import Dataset
import numpy as np
import matplotlib.pyplot as plt
import csv
import collections
import shapefile
#from matplotlib.colors import LogNorm
from matplotlib import cm
#from shapely.geometry import *
from scipy import interpolate
from scipy.ndimage import gaussian_filter
from plastic_utilities_v2 import *
from GL_model_tools import *
from flowline_class_hierarchy import *

##-------------------
### READING IN BED, VELOCITY, SURFACE CHANGE ETC.
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
bb = np.ma.masked_where(thick_mask !=2, b_raw)
## Down-sampling
X = xx[::2]
Y = yy[::2]
S = ss[::2, ::2]
H = hh[::2, ::2] 
B = bb[::2, ::2]
## Not down-sampling
#X = xx
#Y = yy
#S = ss
fh.close()

#Smoothing bed to check effect on dLdt
unsmoothB = B
smoothB = gaussian_filter(B, 2)
#B_processed = np.ma.masked_where(thick_mask !=2, smoothB)

S_interp = interpolate.RectBivariateSpline(X, Y[::-1], S.T[::, ::-1])
H_interp = interpolate.RectBivariateSpline(X, Y[::-1], H.T[::, ::-1])
B_interp = interpolate.RectBivariateSpline(X, Y[::-1], smoothB.T[::, ::-1])

### Reading in SENTINEL velocity map
#print 'Now reading in (vector) velocity map'
#v_path = 'Documents/1. Research/2. Flowline networks/Model/Data/ESA-Greenland/greenland_iv_500m_s1_20161223_20170227_v1_0.nc'
#fh2 = Dataset(v_path, mode='r')
#xv = fh2.variables['x'][:].copy()
#yv = fh2.variables['y'][:].copy()
##yv = yv_flipped[::-1]
#v_raw = fh2.variables['land_ice_surface_velocity_magnitude'][:].copy() #this is v(y, x)
#vx_raw = fh2.variables['land_ice_surface_easting_velocity'][:].copy()
#vy_raw =fh2.variables['land_ice_surface_northing_velocity'][:].copy()
#v_upper = np.ma.masked_greater(v_raw, 10000)
#vx_upper = np.ma.masked_greater(vx_raw, 10000)
#vy_upper = np.ma.masked_greater(vy_raw, 10000)
#fh2.close()
#
### Interpolate SENTINEL and sample at BedMachine points
#print 'Now interpolating to same grid'
#vf_x = interpolate.interp2d(xv, yv[::-1], vx_upper[::-1,::])
#vf_y = interpolate.interp2d(xv, yv[::-1], vy_upper[::-1,::])
#vf = interpolate.interp2d(xv, yv[::-1], v_upper[::-1, ::])

print 'Reading in 5-year surface elevation change'
gl_sec_path ='Documents/GitHub/plastic-networks/Data/CS2-SEC_5yr.nc'
#gl_sec_path ='Documents/GitHub/plastic-networks/Data/CS2-SEC_2yr.nc'
fh3 = Dataset(gl_sec_path, mode='r')
x_sec = fh3.variables['x'][:].copy() #x-coord (polar stereo)
y_sec = fh3.variables['y'][:].copy() #y-coord (polar stereo)
t_sec = fh3.variables['t'][:].copy() #average time of slice (days since 1 JAN 2000)
sec_raw = fh3.variables['SEC'][:].copy()
fh3.close()

sec_i_masked = np.ma.masked_greater(sec_raw[:,:,0], 9000)
sec_i_excludemasked = np.ma.filled(sec_i_masked, fill_value=np.mean(sec_i_masked))
#sec_i_regrid = interpolate.griddata((x_sec.ravel(), y_sec.ravel()), sec_i_masked.ravel(), (Xmat, Ymat), method='nearest')
SEC_i = interpolate.RectBivariateSpline(x_sec, y_sec, sec_i_excludemasked.T)


print 'Reading in MEaSUREs reference file' 
gl_gid_fldr = 'Documents/GitHub/plastic-networks/Data/MEaSUREs-GlacierIDs'
sf_ref = shapefile.Reader(gl_gid_fldr+'/GlacierIDs_v01_2') #Specify the base filename of the group of files that makes up a shapefile


## Reading terminus positions consistently
def read_termini(filename, year):
    """Make a dictionary of terminus positions, indexed by MEaSUREs ID. Outputs dictionary"""
    print 'Reading in MEaSUREs terminus positions for year ' + str(year)
    sf = shapefile.Reader(filename)
    fields = sf.fields[1:] #excluding the mute "DeletionFlag"
    field_names = [field[0] for field in fields]
    term_recs = sf.shapeRecords()
    termpts_dict = {}
    for r in term_recs:
        atr = dict(zip(field_names, r.record)) #dictionary of shapefile fields, so we can access GlacierID by name rather than index.  Index changes in later years.
        key = atr['GlacierID'] #MEaSUREs ID number for the glacier, found by name rather than index
        termpts_dict[key] = np.asarray(r.shape.points) #save points spanning terminus to dictionary
    return termpts_dict

gl_termpos_fldr = 'Documents/GitHub/plastic-networks/Data/MEaSUREs-termini'
basefiles = ['/termini_0001_v01_2', '/termini_0506_v01_2', '/termini_0607_v01_2', '/termini_0708_v01_2', '/termini_0809_v01_2', '/termini_1213_v01_2', '/termini_1415_v01_2', '/termini_1516_v01_2', '/termini_1617_v01_2']
years = [2000, 2005, 2006, 2007, 2008, 2012, 2014, 2015, 2016]

termini = {}
for i,b in enumerate(basefiles):
    yr = years[i]
    fn = gl_termpos_fldr+b
    termini[yr] = read_termini(fn, yr) #creating dictionary for each year
    print len(termini[yr])
    
## Test earliest year of appearance for each glacier
master_initial_termini = {}
keys_05 = []
keys_06 = []
keys_07 = []
keys_08 = []
keys_12 = []

for k in termini[2014].keys():
    if k in termini[2000].keys():
        master_initial_termini[k] = termini[2000][k]
    elif k in termini[2005].keys():
        print 'Glacier ID ' + str(k) + ' taken from year 2005'
        master_initial_termini[k] = termini[2005][k]
        keys_05.append(k)
    elif k in termini[2006].keys():
        print 'Glacier ID ' + str(k) + ' taken from year 2006'
        master_initial_termini[k] = termini[2006][k]
        keys_06.append(k)
    elif k in termini[2007].keys():
        print 'Glacier ID ' + str(k) + ' taken from year 2007'
        master_initial_termini[k] = termini[2007][k]
        keys_07.append(k)
    elif k in termini[2008].keys():
        print 'Glacier ID ' + str(k) + 'taken from year 2008'
        master_initial_termini[k] = termini[2008][k]
        keys_08.append(k)
    elif k in termini[2012].keys():
        print 'Glacier ID ' + str(k) + ' taken from year 2012'
        master_initial_termini[k] = termini[2012][k]
        keys_12.append(k)
    else:
        print 'Glacier ID ' + str(k) + ' not found'
    

#print 'Reading in MEaSUREs terminus positions for year 2000'
#gl_termpos_fldr = 'Documents/GitHub/plastic-networks/Data/MEaSUREs-termini'
#sf_termpos = shapefile.Reader(gl_termpos_fldr+'/termini_0001_v01_2') #Specify the base filename of the group of files that makes up a shapefile

print 'Reading in MEaSUREs terminus positions for year 2014'
gl_termpos_fldr = 'Documents/GitHub/plastic-networks/Data/MEaSUREs-termini'
sf_termpos_1415 = shapefile.Reader(gl_termpos_fldr+'/termini_1415_v01_2') #Specify the base filename of the group of files that makes up a shapefile

print 'Reading in MEaSUREs terminus positions for year 2015'
gl_termpos_fldr = 'Documents/GitHub/plastic-networks/Data/MEaSUREs-termini'
sf_termpos_1516 = shapefile.Reader(gl_termpos_fldr+'/termini_1516_v01_2') #Specify the base filename of the group of files that makes up a shapefile


##-------------------
### FINDING GLACIERS
##-------------------

#jakcoords_main = Flowline_CSV('Documents/GitHub/plastic-networks/Data/jakobshavn-mainline-w_width.csv', 1, has_width=True, flip_order=False)[0]
#jak_0 = Flowline(coords=jakcoords_main, index=0, name='Jak mainline', has_width=True)
#Jakobshavn_main = PlasticNetwork(name='Jakobshavn Isbrae [main/south]', init_type='Flowline', branches=(jak_0), main_terminus=jakcoords_main[0])
#Jakobshavn_main.load_network(filename='JakobshavnIsbrae-main_south.pickle')
#
#jakcoords_sec = Flowline_CSV('Jakobshavn_secondary-flowline-w_width.csv', 1, has_width=True, flip_order=True)[0]
#jak_1 = Flowline(coords=jakcoords_sec, index=0, name='Jak secondary branch', has_width=True)
#Jakobshavn_sec = PlasticNetwork(name='Jakobshavn Isbrae [secondary/central]', init_type='Flowline', branches=(jak_1), main_terminus=jakcoords_sec[0])
#Jakobshavn_sec.load_network(filename='Jakobshavn_sec.pickle')
#
#jakcoords_tert = Flowline_CSV('Jakobshavn_tertiary-flowline-w_width.csv', 1, has_width=True, flip_order=True)[0]
#jak_2 = Flowline(coords=jakcoords_tert, index=0, name='Jak tertiary branch', has_width=True)
#Jakobshavn_tert = PlasticNetwork(name='Jakobshavn Isbrae [tertiary/north]', init_type='Flowline', branches=(jak_2), main_terminus=jakcoords_tert[0])
#Jakobshavn_tert.load_network(filename='Jakobshavn_tert.pickle')
#
#kbcoords = Flowline_CSV('KogeBugt-mainline-w_width.csv', 1, has_width=True, flip_order=True)[0]
#kb_line = Flowline(coords=kbcoords, index=0, name='Koge Bugt mainline', has_width=True)
#KogeBugt = PlasticNetwork(name='Koge Bugt', init_type='Flowline', branches=(kb_line), main_terminus=kbcoords[0])
#KogeBugt.load_network(filename='KogeBugt.pickle')
#
##
##### INTERSECTING LINES
#helcoords_0, helcoords_1, helcoords_2 = Flowline_CSV('Helheim-network-w_width.csv', 3, has_width=True, flip_order=False)
#hel_0 = Branch(coords=helcoords_0, index=0, order=0)
#hel_1 = Branch(coords=helcoords_1, index=1, order=1, flows_to=0)
#hel_2 = Branch(coords=helcoords_2, index=2, order=1, flows_to=0)
#hel_branches = (hel_0, hel_1, hel_2)
#Helheim = PlasticNetwork(name='Helheim', init_type='Branch', branches=hel_branches, main_terminus=helcoords_0[0])
#Helheim.make_full_lines()
#Helheim.load_network(filename='Helheim.pickle')
#
#kangercoords_0, kangercoords_1, kangercoords_2, kangercoords_3, kangercoords_4 = Flowline_CSV('Documents/GitHub/plastic-networks/Data/kangerlussuaq-network-w_width.csv', 5, has_width=True, flip_order=False)
#kanger_0 = Branch(coords=kangercoords_0, index=0, order=0)
#kanger_1 = Branch(coords=kangercoords_1, index=1, order=1, flows_to=0, intersect=174)
##kanger_2 = Branch(coords=kangercoords_2, index=2, order=1, flows_to=0, intersect=191) #DIFFERENT FROM PREVIOUS BRANCH 2.  NEW FLOWLINE SET AS OF 31 MAR 2018
#kanger_3 = Branch(coords=kangercoords_3, index=3, order=1, flows_to=0, intersect=146)
#kanger_4 = Branch(coords=kangercoords_4, index=4, order=1, flows_to=0, intersect=61)
#kanger_branches = (kanger_0, kanger_1, kanger_3, kanger_4)
#Kanger = PlasticNetwork(name='Kangerlussuaq', init_type='Branch', branches=kanger_branches, main_terminus=kangercoords_0[0])
#Kanger.make_full_lines()
#Kanger.load_network(filename='Kangerlussuaq.pickle')
#
#
###-------------------
#### PROCESSING LINE FUNCTIONS + OPTIMIZING YIELD
###-------------------
#
#glacier_networks = (Jakobshavn_main, Jakobshavn_sec, Jakobshavn_tert, KogeBugt, Helheim, Kanger) #list which glaciers we're handling
##glacier_networks=(Jakobshavn_main,)
#
#for gl in glacier_networks:
#    print gl.name
#    gl.process_full_lines(B_interp, S_interp, H_interp)
#    #if gl in (KogeBugt, Kanger): # Add more sophisticated code to catch warnings?
#    #    gl.remove_floating()
#    #    if gl in (Kanger,):
#    #        gl.make_full_lines()
#    #    else:
#    #        pass
#        #gl.process_full_lines(B_interp, S_interp, H_interp)
#    #gl.optimize_network_yield(check_all=False)
#    for fln in gl.flowlines:
#        fln.yield_type  = gl.network_yield_type
#        fln.optimal_tau = gl.network_tau
#    gl.network_ref_profiles()