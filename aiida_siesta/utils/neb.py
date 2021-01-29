
def parse_neb_results(file, traj_in):
    """
    Parses NEB.results 
    :param: file: NEB results
    :param: traj_in: TrajectoryData object with final MEP images

    :return: Extended trajectory object with NEB data arrays
             and estimation of barrier, and number of iterations.
    """
    import numpy as np

    n_images=traj_in.numsteps

    # digest the whole file
    
    data = np.loadtxt(file)

    number_of_neb_iterations = int(len(data) / n_images)

    # Get the data for the final iteration
    final=data[-n_images:]

    # Create a new object for hygiene
    traj = traj_in.clone()

    energies = final[:,2]
    min_neb=max(energies)
    max_neb=min(energies)
    barrier=abs(max_neb-min_neb)
    
    traj.set_attribute('barrier', barrier)
    traj.set_attribute('neb_iterations', number_of_neb_iterations)
    traj.set_array('reaction_coordinates', final[:,1])
    traj.set_array('energies', energies)
    traj.set_array('ediff', final[:,3])
    traj.set_array('curvature', final[:,4])
    traj.set_array('max_force', final[:,5])

    return traj

def plot_neb(traj):

    import os, shutil
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.interpolate import interp1d
    from scipy import interpolate

    im = traj.get_array('steps') 
    x  = traj.get_array('reaction_coordinates') 
    y  = traj.get_array('ediff') 
    y2 = traj.get_array('energies') 

    barrier = round(traj.get_attribute('barrier'),3)
    
    xnew = np.linspace(0, x[len(x)-1], num=1000, endpoint=True)
    f1=interp1d(x, y, kind='linear')
    f2=interp1d(x, y, kind='cubic')
    f3=interp1d(x, y, kind='quadratic')
    plt.plot(x,y,"o",xnew,f1(xnew),"-",xnew,f2(xnew),"--",xnew,f3(xnew),'r')
    plt.title("Barrier Energy = "+str(barrier)+" eV")
    plt.legend(['data', 'linear', 'cubic','quadratic'], loc='best')

    plt.savefig("NEB.png")
    plt.show()
