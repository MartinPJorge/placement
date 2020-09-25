library(ggmap)
library(dismo)


# Read the micro cells
wifis <- read.csv(file="valencia-haven-wifi-aps.csv", header=TRUE, sep = ',')


######### CIRCLE CONTOUR ###########
#################################################################################
# create circles data frame from the centers data frame
make_circles <- function(centers, radius, nPoints = 100){
  # centers: the data frame of centers with ID
  # radius: radius measured in kilometer
  #
  meanLat <- mean(centers$latitude)
  # length per longitude changes with lattitude, so need correction
  radiusLon <- radius /111 / cos(meanLat/57.3)
  radiusLat <- radius / 111
  circleDF <- data.frame(ID = rep('sample', each = nPoints))
  circleDF$fillcolor <- centers$fillcolor
  angle <- seq(0,2*pi,length.out = nPoints)
  
  circleDF$lon <- unlist(lapply(centers$longitude, function(x) x + radiusLon * cos(angle)))
  circleDF$lat <- unlist(lapply(centers$latitude, function(x) x + radiusLat * sin(angle)))
  return(circleDF)
}




w80211n <- subset(wifis, technology == '802.11n')
w80211ac <- subset(wifis, technology == '802.11ac')



# obtain covarage circles
# w80211ac_circles <- make_circles(w80211ac, w80211ac$radius)
# w80211n_circles <- make_circles(w80211n, w80211n$radius)


## Get the map
# bl <- 39.419224, -0.343373
# tr <- 39.437913, -0.302092
haven_borders <- c(bottom = 39.419224, top = 39.437913,
                   left = -0.341373, right = -0.304092)
map <- get_stamenmap(haven_borders, zoom=16, maptype = "toner-lite")
map_valencia_haven <- ggmap(map)




# Plot the coverage circles
for (i in 1:nrow(w80211n)) {
  w80211n_wifi <- w80211n[i,]
  w80211n_circle <- make_circles(w80211n_wifi, w80211n_wifi$radius/1e3)
  map_valencia_haven <- map_valencia_haven + geom_polygon(data=w80211n_circle,
                                                          aes(x=lon, y=lat),
                                          fill='#B2E7C9',alpha=0.5,
                                          linetype='dashed', color='#6BB694')
}
for (i in 1:nrow(w80211ac)) {
  w80211ac_wifi <- w80211ac[i,]
  w80211ac_circle <- make_circles(w80211ac_wifi, w80211ac_wifi$radius/1e3)
  map_valencia_haven <- map_valencia_haven + geom_polygon(data=w80211ac_circle,
                                                          aes(x=lon, y=lat),
                                          fill='#BED7EF',alpha=0.7,
                                          linetype='dotdash', color='#567993')
}
map_valencia_haven

