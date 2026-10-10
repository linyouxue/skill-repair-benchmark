# Attitude Inner Loop: Planner and PID

## Purpose
Guide the design of a quadrotor inner loop: the attitude planner (desired lateral acceleration to desired roll/pitch) and the attitude PID (Euler angle error to body moments), with gain sizing tied to trajectory demand.

## When to Use
Use when choosing, implementing, or tuning the attitude planner or attitude PID. Do not use for position-loop gains, trajectory parsing, motor mixing, or artifact formatting; those belong to other skills.

## Procedure
- Attitude planner: given desired lateral acceleration (ax, ay), current yaw psi, and gravity g, set phi_des proportional to (ax*sin(psi) - ay*cos(psi))/g and theta_des proportional to (ax*cos(psi) + ay*sin(psi))/g. Pass desired yaw and yaw rate through. Choose any function signature consistent with the surrounding code.
- Attitude PID: compute e = desired_rot - current_rot, update integral_e += e*dt with dt = 1.0/params['sample_rate'], and output M = I @ (kp*e + ki*integral_e + kd*(desired_omega - current_omega)) with kp, ki, kd as length-3 arrays applied element-wise before the inertia multiply.
- Size attitude bandwidth to trajectory demand: estimate peak lateral acceleration a_peak from the planned trajectory and the allowed tilt error delta_theta. Require sqrt(kp_att[x]) and sqrt(kp_att[y]) to exceed a_peak / (g * delta_theta) by a healthy margin; raise kd_att[x,y] in rough proportion to keep damping. Yaw gains can be lower.
- Diagnose from residuals, not from priors: run a short simulation. If horizontal fly commands show growing lateral tracking error, raise kp_att[x,y] (and kd_att[x,y]) before touching position-loop gains. If steady-state Euler error persists on a sustained command, add small ki on that axis; otherwise keep ki at zero.

## Constraints / Pitfalls
- Create integral state (zeros(3)) fresh before each simulation run; never store it in a mutable default argument.
- Do not hardcode dt, sample rate, inertia, or specific gain literals; derive dt from params and treat gains as tunables sized by the bandwidth rule above.
- Keep ki small or zero unless observed steady-state error on that axis justifies it; attitude integral wind-up manifests as x/y oscillation during z-only maneuvers.