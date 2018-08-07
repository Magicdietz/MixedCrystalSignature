#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  3 11:10:35 2018

@author: dietz
"""

import numpy as np
from scipy.spatial import ConvexHull
import numba
from math import sqrt,atan2,acos,pi
from sphericalharmonics.sphharmhard import sph_harm_hard
from functools import partial

try:
    import multiprocessing as mp
    MP_EXISTS=False
except ImportError:
    MP_EXISTS=False

def get_inner_volume_bool_vec(datapoints,volume):
    x_min, x_max = volume[0]
    y_min, y_max = volume[1]
    z_min, z_max = volume[2]
    
    bool_matrix_min = datapoints >= [x_min,y_min,z_min]
    bool_matrix_max = datapoints <= [x_max,y_max,z_max]
    
    bool_matrix=np.logical_and(bool_matrix_min,bool_matrix_max)
    
    return np.all(bool_matrix,axis=1)

@numba.njit(numba.float64(numba.float64[:],numba.float64[:]))
def calc_area(u,v):
    cx=u[1]*v[2]-u[2]*v[1]
    cy=u[2]*v[0]-u[0]*v[2]
    cz=u[0]*v[1]-u[1]*v[0]
    
    return 0.5*sqrt(cx**2+cy**2+cz**2)

@numba.njit(numba.float64[:,:](numba.int64,numba.float64[:,:],numba.int32[:,:],numba.float64[:,:]))
def calc_voro_area_angle(n_faces, norm_vecs,simpls,points):
    u_vec=np.zeros((3,),dtype=np.float64)
    v_vec=np.zeros((3,),dtype=np.float64)
    result_array = np.zeros((n_faces, 3),dtype=np.float64)
    for i in range(n_faces):
        for j in range(3):
            u_vec[j] = points[simpls[i,1],j]-points[simpls[i,0],j]
            v_vec[j] = points[simpls[i,2],j]-points[simpls[i,0],j]
        result_array[i,0]=calc_area(u_vec,v_vec)
        #phi - azimuthal angle
        result_array[i,1]=atan2(norm_vecs[i, 1], norm_vecs[i, 0])%(2*pi)
        #theta - polar angle
        result_array[i,2]=acos(norm_vecs[i,2])
        
    return result_array

def calc_voro_area_angles(conv_hulls):
    voro_area_angles=[]
    for hull in conv_hulls:
        voro_area_angle=calc_voro_area_angle(hull.simplices.shape[0],hull.equations[:,0:3],
                                             hull.simplices,hull.points)
        voro_area_angles.append(voro_area_angle)
    return voro_area_angles

def calc_convex_hulls(indices,regions,point_region,vertices):
    
    voro_points_list=[vertices[regions[point_region[i]]] for i in indices]
    
    if MP_EXISTS:
        p=mp.Pool()
        return p.map(partial(ConvexHull,qhull_options="QJ"),voro_points_list,chunksize=400)
        p.close()
        p.terminate()
        p.join()
    else:
        return [ConvexHull(voro_points_list[i],qhull_options="QJ") for i in indices]

@numba.njit(numba.complex128[:](numba.int64,numba.int32[:],numba.float64[:],numba.float64[:],numba.float64,numba.float64[:]))
def calc_msm_qlm(len_array,l_vec,theta_vec,phi_vec,total_area,areas):
    len_l=l_vec.shape[0]
    len_angles=theta_vec.shape[0]
    
    qlm_result = np.zeros(len_array,dtype=np.complex128)
    for i in range(len_angles):
        index_l=0
        for j in range(len_l):
            l=l_vec[j]
            for m in range(-l,l+1):
                ylm=sph_harm_hard(l,m,theta_vec[i],phi_vec[i])
                qlm_result[index_l+m+l]+=ylm*areas[i]
            index_l+=2*l+1
            
    for i in range(len_array):
        qlm_result[i]/=total_area
        
    return qlm_result

def calc_qlm_array(total_areas,voro_area_angles,l_vec):
    len_array=0 
    for i in range(l_vec.shape[0]): 
        len_array += (2*l_vec[i]+1) 
        
    qlm_arrays=np.zeros((len(total_areas),len_array),dtype=np.complex128) 
    
    for i in range(len(total_areas)):
        qlm_arrays[i,:]=calc_msm_qlm(len_array,l_vec,voro_area_angles[i][:,2],voro_area_angles[i][:,1],total_areas[i],voro_area_angles[i][:,0])  
    
    return qlm_arrays

@numba.njit(numba.float64(numba.int64,numba.complex128[:],numba.int64,numba.complex128[:,:]))
def calc_si(l,qlms,len_neigh,qlms_neigh):
    
    qlm_sum=0.
    for m in range(2*l+1):
        qlm_sum+=abs(qlms[m])**2
    qlm_sum=sqrt(qlm_sum)
    
    si=0.
    for i in range(len_neigh):
        qlm_sum_neigh=0.
        for m in range(2*l+1):
            qlm_sum_neigh+=abs(qlms_neigh[i,m])**2
        qlm_sum_neigh=sqrt(qlm_sum_neigh)
        si_inner=0.
        for m in range(2*l+1):
            si_inner+=(qlms[m]*qlms_neigh[i,m].conjugate()).real
        si+=si_inner/(qlm_sum*qlm_sum_neigh)

    return si/len_neigh

if __name__=='__main__':
    from datageneration.generatecrystaldata import fill_volume_fcc
    from scipy.spatial import Voronoi
    import time
    
    t_tot=time.process_time()
    
    size=[15,15,15]
    datapoints=fill_volume_fcc(size[0], size[1], size[2])
    volume=[[2,size[i]-2] for i in range(3)]
    
    l_vec=np.array([2,4,6],dtype=np.int32) 
    inner_bool = get_inner_volume_bool_vec(datapoints,volume)
    
    voro=Voronoi(datapoints)
    regions=voro.regions
    point_region=voro.point_region
    vertices=voro.vertices
    indices = np.arange(0, len(datapoints), dtype=np.int32)
    
    t=time.process_time()
    conv_hulls=calc_convex_hulls(indices,regions,point_region,vertices)
    print('calc_convex_hulls',time.process_time()-t)
    t=time.process_time()
    voro_area_angles=calc_voro_area_angles(conv_hulls)
    print('calc_voro_area_angles',time.process_time()-t)
    
    t=time.process_time()
    total_areas=[hull.volume for hull in conv_hulls]
    voro_vols=[hull.volume for hull in conv_hulls]
    qlm_arrays=calc_qlm_array(total_areas,voro_area_angles,l_vec)
    print('calc_qlm_array',time.process_time()-t)
    
    print('total time:',time.process_time()-t_tot)