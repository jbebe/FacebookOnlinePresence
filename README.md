# <img src="http://i.imgur.com/eVrmv6B.png" height="50"/> Facebook Online Presence
# (I tested it so now it's official. It does not work anymore)
### (made in 2016 so it is kinda out of date with respect to facebook's api)

### Introduction

This script is a heavily modified version of
[defaultnamehere's zzzzz](https://github.com/defaultnamehere/zzzzz) (a.k.a. Stalky)
I rewrote to make it better* on both back and front end.
*more features

### Backstory

I wanted to create a nice diagram of how my friends show up on and log out of facebook.
First I used Tampermonkey and jQuery to save presence to localStorage and show the result
on facebook itself. Then I realized I have to close the browser once in a while so this
isn't the right approach. Somehow I found Stalky but I wanted to make it better so now it is better.

### Features

* every useful message from the /pull feed is parsed (not just chatproxy-presence)
  * chatproxy-presence
  * buddylist_overlay
  * t_tp
  * delta
  * typ
  * inbox
* direct query of UID presence if no presence information is received during a custom time period
* direct query of avatar url and full name


### Web Interface

![interface](http://i.imgur.com/oekoSDF.png)

### TODO

?
