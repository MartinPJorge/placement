Creator "igraph version 1.2.4 Wed Apr 17 15:52:47 2019"
Version 1
graph
[
  directed 0
  node
  [
    id 1
    name "robotSlave"
    demand 1
    type "vnf"
    lon -3.75591113449374
    lat 40.2753689393847
    cpu 0
    mem 0
    disk 0
    radio ""
    maxInstances 1
  ]
  node
  [
    id 2
    name "robotMaster"
    demand 1
    type "vnf"
    lon -3.74711856588699
    lat 40.2628525915245
    cpu 0
    mem 0
    disk 0
    radio ""
    maxInstances 1
  ]
  node
  [
    id 3
    name "vEPC"
    demand 2
    type "vnf"
    lon -3.74724049236494
    lat 40.2753268113271
    cpu 2
    mem 20
    disk 0
    radio ""
    maxInstances 1
    vnfTime 1
  ]
  node
  [
    id 4
    name "controller"
    demand 2
    type "vnf"
    lon -3.7653011855024
    lat 40.2695626631112
    cpu 2
    mem 20
    disk 0
    radio ""
    maxInstances 1
    vnfTime 1
  ]
  edge
  [
    source 1
    target 2
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
  edge
  [
    source 2
    target 3
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
  edge
  [
    source 3
    target 4
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
]
