## Loading in MEaSUREs terminus position data for Greenland to assess utility for validating hindcasts
## 12 Sept 2018  EHU
## 20 Mar 2019 edit: use these functions to compare 2006-2014 termini with hindcasted
## 13 Nov 2019: editing plots to address GRL review comments

from netCDF4 import Dataset
import numpy as np
import matplotlib.pyplot as plt
import csv
import collections
import shapefile
import glob
#from matplotlib.colors import LogNorm
from matplotlib import cm
#from shapely.geometry import *
from scipy import interpolate
from scipy.ndimage import gaussian_filter
from scipy.stats import gaussian_kde
from osgeo import gdal
from mpl_toolkits.basemap import Basemap
import mpl_toolkits.basemap.pyproj as pyproj
import shapely.geometry as geom
## Special import for SERMeQ modules
import sys
sys.path.insert(0, 'Documents/GitHub/plastic-networks')
from SERMeQ.plastic_utilities_v2 import *
from SERMeQ.GL_model_tools import *
from SERMeQ.flowline_class_hierarchy import *


##-------------------
### READING IN OBS
##-------------------

print 'Reading MEaSUREs velocities'
x_comp, y_comp, v_comp_raw = read_velocities('Documents/GitHub/Data_unsynced/gld-velocity-composite-10Jan19.tif')
vx_comp_raw = read_velocities('Documents/GitHub/Data_unsynced/gld-x_velocity-composite-10Jan19.tif', return_grid=False)
vy_comp_raw = read_velocities('Documents/GitHub/Data_unsynced/gld-y_velocity-composite-10Jan19.tif', return_grid=False)
v_comp = np.ma.masked_invalid(v_comp_raw)
vx_comp = np.ma.masked_invalid(vx_comp_raw)
vy_comp = np.ma.masked_invalid(vy_comp_raw)
v_excludemasked = np.ma.filled(v_comp, fill_value=0)
vx_excludemasked = np.ma.filled(vx_comp, fill_value=0)
vy_excludemasked = np.ma.filled(vy_comp, fill_value=0)
days_per_annum = 365.242 #need to convert units of MEaSUREs velocity to align with what we used from Sentinel before
v_a2d = np.array(v_excludemasked) / days_per_annum
vx_a2d = np.array(vx_excludemasked) / days_per_annum
vy_a2d = np.array(vy_excludemasked) / days_per_annum


print 'Interpolating MEaSUREs velocity composites for tracing'
x_flat = x_comp[0,:]
y_flat = y_comp[:,0]
func_vxcomp = interpolate.interp2d(x_flat, y_flat[::-1], vx_a2d) #these need to be flipped along y-axis
func_vycomp = interpolate.interp2d(x_flat, y_flat[::-1], vy_a2d)
func_vcomp = interpolate.interp2d(x_flat, y_flat[::-1], v_a2d)

print 'Reading in MEaSUREs reference file' 
gl_gid_fldr = 'Documents/GitHub/Data_unsynced/MEaSUREs-GlacierIDs'
sf_ref = shapefile.Reader(gl_gid_fldr+'/GlacierIDs_v01_2') #Specify the base filename of the group of files that makes up a shapefile

gl_termpos_fldr = 'Documents/GitHub/Data_unsynced/MEaSUREs-termini'
basefiles = ['/termini_0001_v01_2', '/termini_0506_v01_2', '/termini_0607_v01_2', '/termini_0708_v01_2', '/termini_0809_v01_2', '/termini_1213_v01_2', '/termini_1415_v01_2', '/termini_1516_v01_2', '/termini_1617_v01_2']
years = [2000, 2005, 2006, 2007, 2008, 2012, 2014, 2015, 2016]

termini = {}
for i,b in enumerate(basefiles):
    yr = years[i]
    fn = gl_termpos_fldr+b
    termini[yr] = read_termini(fn, yr) #creating dictionary for each year
    print len(termini[yr])
    
## Find centroid rates of retreat for observed period 2006-2014
def Centroid_dLdt(termpts1, termpts2, time_interval, vx_func, vy_func):
    """Given two arrays of terminus-spanning coordinates, finds the distance between their centroids and converts to a retreat rate in the given time_interval.
    Returns retreat rate in distance per annum - check that termpts are in units of km (UTM) and time_interval in anni
    Inputs:
        termpts1 - points describing terminus at time t1
        termpts2 - points describing terminus at time t2
        time_interval - interval in anna, t2-t1
        vx_func - a 2D interpolated function for the x-component of ice velocity, used to determine sign of dL/dt
        vy_func - a 2D interpolated function for the y-component of ice velocity
    """
    term1 = geom.LineString(termpts1)
    term1_centr = term1.centroid
    centr1_coords = np.squeeze(list(term1_centr.coords))
    term2 = geom.LineString(termpts2)
    term2_centr = term2.centroid
    centr2_coords = np.squeeze(list(term2_centr.coords))
    
    disp_vector = centr1_coords - centr2_coords
    termchange = np.linalg.norm(disp_vector)
    dLdt_abs = termchange / time_interval
    
    v_vector = (vx_func(centr1_coords[0], centr1_coords[1]), vy_func(centr1_coords[0], centr1_coords[1]))
    dotprod = np.vdot(disp_vector, v_vector)
    sgn_dL = sign(dotprod) #sign of dot product indicates whether displacement of termini is parallel to velocity (advance) or antiparallel (retreat)
    
    return dLdt_abs*sgn_dL
    
obs_retreat_rates = {yr:{} for yr in years[1::]}
for i in range(1, len(years)):
    current_termini = termini[years[i]]
    previous_termini = termini[years[i-1]]
    for gid in current_termini.keys():
        try:
            term1 = current_termini[gid]
            term2 = previous_termini[gid]
            obs_retreat_rates[years[i]][gid] = Centroid_dLdt(term1, term2, time_interval=years[i]-years[i-1], vx_func=func_vxcomp, vy_func=func_vycomp) #calculate retreat rate at each glacier for each year 
        except KeyError:
            print 'No terminus found in year {} for glacier {}'.format(years[i], gid) # happens when glacier terminus is recorded in one year but not the previous


##-------------------
### READING IN SIMS
##-------------------

testyears = arange(0, 9, step=0.25)#array of the years tested, with year "0" reflecting initial nominal date of MEaSUREs read-in (generally 2006)
scenarios = ('persistence', 
#'RCP4pt5', 
#'RCP8pt5'
)

#datemarker = '2019-02-08' #markers on filename to indicate date run
tempmarker = 'min10Cice' #and temperature of ice
timestepmarker = '8a_dt025a' #and total time and timestep

## Define which glaciers are in the simulated set
glacier_ids = range(1,195) #MEaSUREs glacier IDs to process.
not_present = (93, 94, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 169) #glacier IDs missing from set
added_jan19 = (139, 140, 141, 142, 143, 159, 161, 172, 173, 177)
errors = (5, 17, 18, 19, 29, 51, 71, 92, 95, 97, 100, 101, 102, 106, 107, 108, 109, 110, 113, 115, 117, 120, 121, 134, 168, 171) #glacier IDs that crashed in hindcasting 12 Mar 2019 *or* showed network problems 21 May 2019
rmv = np.concatenate((not_present, errors))
for n in rmv:
    try:
        glacier_ids.remove(n)
    except ValueError:
        pass
glaciers_simulated = glacier_ids #adjust this to reflect whether you want to examine the whole set or a subset


full_output_dicts = {}
for s in scenarios:
    scenario_output = {'Testyears': testyears}
    for gid in glaciers_simulated:
        fn = glob.glob('Documents/GitHub/Data_unsynced/Hindcasted_networks/GID{}-*-{}-{}-{}.pickle'.format(gid, s, tempmarker, timestepmarker))[0] #using glob * to select files of multiple run dates
        lightload(fn, glacier_name = 'GID{}'.format(gid), output_dictionary = scenario_output)
    full_output_dicts[s] = scenario_output #add output from this scenario to the dictionary of all output, with scenario name as key


##-------------------
### COMPARE OBS-SIMS
##-------------------
avg_obs_rates = [] #aggregating observations to plot distribution
for gid in glaciers_simulated:
    obsrates = []
    for yr in years[2::]:
        try:
            obsrates.append(obs_retreat_rates[yr][gid])
        except KeyError: #if no observation exists for this year on this glacier
            pass
    avg_obs = np.mean(obsrates)
    avg_obs_rates.append(avg_obs)

avg_sim_rates = []
for gid in glaciers_simulated:
    sim_termini = full_output_dicts['persistence']['GID{}'.format(gid)][0]['Termini'][1::]
    cumulative_dL = -1*float(sim_termini[-1]) #terminus positions given in arclength upglacier from initial terminus, so negative final terminus position corresponds to positive dL and vice versa
    cumulative_dt = float(testyears[-1])
    avg_dLdt = cumulative_dL/cumulative_dt
    avg_sim_rates.append(avg_dLdt)

obs_total = 0.00875*np.array(avg_obs_rates) #converting from rates to total retreat in 8.75 yr period, expressed in km rather than m
sim_total = 0.00875*np.array(avg_sim_rates)


## Compare PDFs of total retreat & plot normalized histograms over
obs_weights = np.ones_like(avg_obs_rates)/float(len(avg_obs_rates))
sim_weights = np.ones_like(avg_sim_rates)/float(len(avg_sim_rates))
obs_dL_dens = gaussian_kde(obs_total) #estimate density of total observed retreat
sim_dL_dens = gaussian_kde(sim_total)
xs2 = np.linspace(-20, 5, 200) #space of dL/dt in km/a
dL_plotting_bins = (-20, -17.5, -15, -12.5, -10, -7.5, -5, -2.5, 0.01, 2.5)
plt.figure()
plt.hist(obs_total, weights = obs_weights, bins=dL_plotting_bins, color='SeaGreen', alpha=0.3)
plt.hist(sim_total, weights = sim_weights, bins=dL_plotting_bins, color='Indigo', alpha=0.3)
plt.plot(xs2, obs_dL_dens(xs2), color='SeaGreen', lw=3.0, label= 'MEaSUREs')
plt.plot(xs2, sim_dL_dens(xs2), color='Indigo', lw=3.0, label='SERMeQ')
plt.xlabel('Total $\Delta$L [km]', fontsize=18)
plt.ylabel('Density', fontsize=18)
plt.legend(loc='upper left')
plt.axes().tick_params(axis='both', length=5, width=2, labelsize=16)
plt.axes().set_yticks([0, 0.25, 0.5, 0.75, 1.0])
plt.axes().set_ylim(0, 1)
plt.show()


## REMOVED 13 NOV
### Histogram of difference
#diff_bins = np.linspace(-2000, 2500, num=29) #select number of bins so that each is ~150 m/a
#plt.figure('Difference observed - simulated retreat rates, Greenland outlets 2006-2014')
#plt.hist(np.array(avg_obs_rates)-np.array(avg_sim_rates), bins=diff_bins, weights=obs_weights, color='DarkBlue', alpha=0.5)
#plt.axes().tick_params(axis='both', length=5, width=2, labelsize=16)
##plt.axes().set_yticks([0, 0.25, 0.5, 0.75, 1.0])
#plt.axes().set_yticks([0, 0.1, 0.2])
#plt.xlabel('$\Delta dL/dt$ [m/a]', fontsize=18)
#plt.ylabel('Density', fontsize=18)
#plt.show()
### generate figure for inset with smoothed distribution
#diff_dens = gaussian_kde((np.array(avg_obs_rates)-np.array(avg_sim_rates))) # calculate in km/a
#xs2 = np.linspace(-2000, 2500, 200)
#plt.figure('dLdt density inset')
#plt.plot(xs2, diff_dens(xs2), lw=3.0, color='DarkBlue') 
#plt.axes().tick_params(axis='both', length=5, width=2, labelsize=16)
#plt.axes().set_xticks([-2000, 0, 2500])
#plt.axes().set_yticks([0, 0.001])
#plt.show()

## 13 Nov: replace difference with percent error
def percent_error(obs_list, sim_list):
    paired = zip(obs_list, sim_list)
    corrected = [(o, s) for (o, s) in paired if o!=0] # avoid divide-by-zero errors
    perc_err = [(o-s)/abs(o) for (o,s) in corrected]
    return perc_err

pe = percent_error(avg_obs_rates, avg_sim_rates)
pe_weights = np.ones_like(pe)/float(len(pe))
pe_bins = np.linspace(-300, 300, num=30) 
plt.figure('Percent error observed - simulated retreat rates, Greenland outlets 2006-2014')
plt.hist(pe, bins=pe_bins, weights=pe_weights, color='DarkBlue', alpha=0.5)
plt.axes().tick_params(axis='both', length=5, width=2, labelsize=16)
plt.xlabel('Percent error $dL/dt$ [m/a]', fontsize=18)
plt.ylabel('Normalized frequency', fontsize=18)
plt.axes().set_yticks([0, 0.2, 0.4, 0.6, 0.8])
plt.show()
### smoothed distribution for inset
pe_dens = gaussian_kde((pe)) # calculate in km/a
xs3 = np.linspace(-1000, 1000, 200)
plt.figure('dLdt percent error inset')
plt.plot(xs3, pe_dens(xs3), lw=3.0, color='DarkBlue') 
plt.axes().tick_params(axis='both', length=5, width=2, labelsize=16)
#plt.axes().set_xticks([-300, 0, 300])
#plt.axes().set_yticks([0, 0.001])
plt.show()


## Density plot of obs vs simulated rates
avsim = 0.001*np.array(avg_sim_rates)
avobs = 0.001*np.array(avg_obs_rates)
os = np.vstack([avsim, avobs])
z = gaussian_kde(os)(os) #density scale of obs vs. simulated rates
#srt = z.argsort() #sort so that densest will be plotted on top
#avg_obs_rates, avg_sim_rates, z = avg_obs_rates[srt], avg_sim_rates[srt], z[srt]  #returns an error, revisit if needed
xeqy_x = range(-3,2)
xeqy_y = range(-3,2)
plt.figure()
plt.scatter(avobs, avsim, c=cm.get_cmap('Blues')(z), s=50, edgecolor='')
#plt.plot(xeqy_x, xeqy_y, c='b', ls='-.')
plt.axes().set_xlabel('Observed dL/dt [km/a]', size=20)
plt.axes().set_ylabel('Simulated dL/dt [km/a]', size=20)
plt.axes().set_xlim(-1, 0.5)
plt.axes().set_ylim(-3, 0.5)
plt.axes().set_xticks([-1, -0.5, 0, 0.5])
plt.axes().set_yticks([-3, -2, -1, 0])
plt.axes().set_aspect(1)
plt.axes().tick_params(axis='both', length=5, width=2, labelsize=20)
plt.show()

## Plotting terminus change history colored by density of similar histories
retreat_density = gaussian_kde(avg_sim_rates)(avg_sim_rates) #will code retreat histories by number of retreats that end up nearby during simulation
density_colors = cm.get_cmap('Blues')(2000*np.array(retreat_density)) #make an array of colors coded to the density calculated above, scaled by 2000 so they show up
plt.figure()
for j, gid in enumerate(glaciers_simulated):
    term_positions = full_output_dicts['persistence']['GID{}'.format(gid)][0]['Termini'][1::]
    if np.all(np.diff(term_positions)>0) or np.all(np.diff(term_positions)<0) or np.all(np.diff(term_positions)==0): #if monotonic retreat
        pass
    else:
        print gid
        #dc = density_colors[j]
        plt.plot(testyears, -0.001*np.array(term_positions), linewidth=2, label=str(gid))
plt.legend(loc='lower left')
plt.axes().set_xlabel('Year', size=20)
plt.axes().set_xticklabels(['2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014'])
plt.axes().set_xlim(0, 8.75)
plt.axes().set_ylabel('Terminus change [km]', size=20)
plt.axes().tick_params(axis='both', length=5, width=2, labelsize=20)
#plt.axes().set_ylim(-100, 1)
#plt.axes().set_yticks([-75, -50, -25, 0])
plt.title('Simulated terminus retreat of {} Greenland outlet glaciers 2006-2014 ERA-I, Tice=-10 C'.format(len(glaciers_simulated)), fontsize=20)
plt.show()


###-------------------
#### MAP VISUALISATIONS
###-------------------
#termini_toplot = termini[2014]
#
#outlet_locations_latlon = {}
#for gid in termini_toplot.keys():
#    latlon_coords = flowline_latlon(termini_toplot[gid])
#    outlet_locations_latlon[gid] = np.asarray(latlon_coords)
#    
#gld_backdrop = Basemap(projection='npstere', boundinglat=70, lon_0=315, epsg=3413, llcrnrlon=300, llcrnrlat=57, urcrnrlon=20, urcrnrlat=80, resolution='h')
#
#
#### Plot total retreat versus latitude (N/S) or longitude (W/E). 
##plt.figure()
##for j, gid in enumerate(glaciers_simulated):
##    term_positions = full_output_dicts['persistence']['GID{}'.format(gid)][0]['Termini'][1::]
##    lngtd = outlet_locations_latlon[gid][0][0]
##    lttd = outlet_locations_latlon[gid][0][1]
##    plt.scatter(lttd, term_positions[-1])
##plt.title('Total retreat by outlet glacier latitude', fontsize=20)
##plt.show()
##
#
#### Map of total retreat (scales linearly with avg rate as calculated above)
#### Use greenland-outlets-map as basis -- some things initialized there first
##retreat_bins = [-3000, -2500, -2000, -1500, -1000, -500, 0, 500] #bins for average retreat rate
##marker_bins = [abs(r/500)+1 for r in retreat_bins]
##gld_backdrop = Basemap(projection='npstere', boundinglat=70, lon_0=315, epsg=3413, llcrnrlon=300, llcrnrlat=57, urcrnrlon=20, urcrnrlat=80, resolution='h')
##plt.figure()
##gld_backdrop.arcgisimage(service='ESRI_Imagery_World_2D', xpixels=5000)
##for i, gid in enumerate(glaciers_simulated):
##    pt = outlet_locations_latlon[gid][0]
##    retreat_rate = avg_sim_rates[i]
##    #markerscale = abs(retreat_rate/np.mean(avg_sim_rates)) #continuous scale
##    retreatscale = np.digitize(retreat_rate, bins=retreat_bins) 
##    markerscale = marker_bins[retreatscale] #discrete scale
##    advret_color = cm.get_cmap('coolwarm')(sign(avg_sim_rates[i]))
##    gld_backdrop.scatter(pt[0], pt[1], s=100*markerscale, marker='o', color=advret_color, edgecolors='DarkViolet', latlon=True)
##    #    term_marker = gld_backdrop(pt[0], pt[1])
##    #    #offset = 100 * np.mod(k,2)
##    #    plt.annotate(s=str(k), xy=term_marker, fontsize='small', fontweight='demi', color='MediumBlue')
##plt.show()
##
#### Map of obs-sim difference
##plt.figure()
##gld_backdrop.arcgisimage(service='ESRI_Imagery_World_2D', xpixels=5000)
##for i, gid in enumerate(glaciers_simulated):
##    pt = outlet_locations_latlon[gid][0]
##    diff = avg_obs_rates[i] - avg_sim_rates[i]
##    markerscale = abs(diff/np.mean(avg_obs_rates))
##    advret_color = cm.get_cmap('coolwarm')(sign(diff))
##    gld_backdrop.scatter(pt[0], pt[1], s=100*markerscale, marker='o', color='b', edgecolors='DarkViolet', latlon=True)
##    #    term_marker = gld_backdrop(pt[0], pt[1])
##    #    #offset = 100 * np.mod(k,2)
##    #    plt.annotate(s=str(k), xy=term_marker, fontsize='small', fontweight='demi', color='MediumBlue')
##plt.show()
#
#
#### Map highlighting case study glaciers
### Color-code markers with model misfit
##colorscale_arr = np.array(avg_obs_rates)-np.array(avg_sim_rates)
##cm1 = cm.get_cmap('coolwarm')
### Color-code markers with total retreat
#colorscale_arr = sim_total
#cm1 = cm.get_cmap('OrRd_r')
#
##markers
#terminus_pts = np.asarray([outlet_locations_latlon[gid][0] for gid in glaciers_simulated])
#
### color-coded by retreat
##plt.figure()
##gld_backdrop.arcgisimage(service='ESRI_Imagery_World_2D', xpixels=5000)
#### misfit colors
###sc = gld_backdrop.scatter(terminus_pts[:,0], terminus_pts[:,1], latlon=True, s=60, marker='o', color=colorscale_arr, edgecolors='K', cmap=cm1, norm=MidpointNormalize(midpoint=0,vmin=-1500, vmax=2500))
###cbar = plt.colorbar(sc, orientation='horizontal')
#### total retreat colors
##sc = gld_backdrop.scatter(terminus_pts[:,0], terminus_pts[:,1], latlon=True, s=60, marker='o', color=colorscale_arr, edgecolors='face', cmap=cm1, vmin=-15.0, vmax=0.0)
##cbar = plt.colorbar(sc, orientation='horizontal', extend='min', ticks=[-15, -10, -5, 0])
##cbar.ax.set_xticklabels(['-15', '-10', '-5', '0'])
### Now plot the case study glaciers on top
##for j in (3, 137, 175):
##    pt = outlet_locations_latlon[j][0]
##    gld_backdrop.scatter(pt[0], pt[1], s=250, marker='*', color='Yellow', edgecolors='k', latlon=True)
##cbar.ax.tick_params(labelsize=16)
##plt.show()
#
### plain outlet plot for barchart-border map
#plt.figure()
#gld_backdrop.arcgisimage(service='ESRI_Imagery_World_2D', xpixels=5000)
### misfit colors
##sc = gld_backdrop.scatter(terminus_pts[:,0], terminus_pts[:,1], latlon=True, s=60, marker='o', color=colorscale_arr, edgecolors='K', cmap=cm1, norm=MidpointNormalize(midpoint=0,vmin=-1500, vmax=2500))
##cbar = plt.colorbar(sc, orientation='horizontal')
### total retreat colors
#sc = gld_backdrop.scatter(terminus_pts[:,0], terminus_pts[:,1], latlon=True, s=30, marker='d', color='Aqua', edgecolors='b')
## Now plot the ticked glaciers
#for j in np.concatenate(((1,), np.arange(10, 201, 10))):
#    pt = outlet_locations_latlon[j][0]
#    gld_backdrop.scatter(pt[0], pt[1], s=30, marker='*', color='k', edgecolors='k', latlon=True)
#plt.show()
#
#####-----------------------------
#####  REGIONAL PICTURE
#####-----------------------------
##### Bin glaciers into regions
##r1_limits = (1, 18) # Disko GIDs - split with geq lower, less than upper
##r2_limits = (18, 93) # northwest
##r3_limits = (93, 122) # northeast
##r4_limits = (122, 144) # Geikie
##r5_limits = (144, 195) # southeast
##limits = (r1_limits, r2_limits, r3_limits, r4_limits, r5_limits)
##
##region_ids = []
##region_termini = []
##region_dLs = []
##
##for k, rl in enumerate(limits):
##    termini = np.asarray([outlet_locations_latlon[gid][0] for gid in glaciers_simulated if gid>=rl[0] and gid<rl[1]])
##    ids = np.asarray([gid for gid in glaciers_simulated if gid>=rl[0] and gid<rl[1]])
##    sim_dLs = [-0.001*full_output_dicts['persistence']['GID{}'.format(gid)][0]['Termini'][-1] for gid in ids] # net retreat over period, expressed in km
##    region_ids.append(ids)
##    region_termini.append(termini)
##    region_dLs.append(sim_dLs)
##
##    plt.figure('Region {} outlets'.format(k))
##    gld_backdrop.arcgisimage(service='ESRI_Imagery_World_2D', xpixels=5000)
##    sc = gld_backdrop.scatter(termini[:,0], termini[:,1], latlon=True, s=200, marker='o', color=sim_dLs, edgecolors='K', cmap=cm1, vmin=-15.0, vmax=0.0)
##    cbar = plt.colorbar(sc, orientation='horizontal', extend='min', ticks=[-15, -10, -5, 0])
##    cbar.ax.set_xticklabels(['-15', '-10', '-5', '0'])
##    plt.show()