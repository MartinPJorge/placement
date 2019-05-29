Creator "igraph version 1.2.4 Wed Apr 17 15:52:47 2019"
Version 1
graph
[
  directed 1
  node
  [
    id 1
    name "fogEndpoint_test_endpoint_1"
    type "endpoint"
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
    name "fogEndpoint_test_endpoint_2"
    type "endpoint"
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
    name "robot_master"
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
    name "robot_slave"
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
  node
  [
    id 5
    name "access_point"
    type "vnf"
    lon 0
    lat 0
    cpu 2
    mem 20
    disk 0
    radio "LTE"
    maxInstances 1
    vnfTime 1
  ]
  edge
  [
    source 1
    target 3
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
  edge
  [
    source 3
    target 5
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
  edge
  [
    source 5
    target 4
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
  edge
  [
    source 4
    target 2
    bandwidth 5
    bandwidthUnits "Mb/s"
  ]
]
